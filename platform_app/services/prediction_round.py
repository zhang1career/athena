"""
一轮预测流程：按 data_file 版本 + data_patch_batch 版本合成数据，执行预测 → AI 建议。
"""
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from platform_app.models import DataSrc
from platform_app.services.data_src_url import resolve_data_src_url
from platform_app.repos.experiment_repo import (
    create_run,
    get_run,
    update_run_status,
    update_run_params,
)
from platform_core.experiment.runner import ExperimentConfig
from platform_app.services.experiment_runner import get_runner
from platform_app.services.worldcup_data_versioning import (
    fetch_full_records,
    load_composed_records,
    list_patch_batches,
    now_version_v,
    save_full_snapshot,
    save_incremental_patches,
    write_composed_records_file,
)

logger = logging.getLogger(__name__)

WORKFLOW_TYPE = "workflow_type"
WORKFLOW_PHASE = "workflow_phase"
AI_SUGGESTIONS = "ai_suggestions"
ROUND_DATA_SOURCE_ID = "round_data_source_id"
DATA_VERSION_V = "data_version_v"
DATA_SRC_ID = "data_src_id"
UPDATE_PATCH_COUNT = "update_patch_count"

PHASE_RUNNING = "running"
PHASE_AI_SUGGESTIONS_PENDING = "ai_suggestions_pending"
PHASE_IMPROVING = "improving"
PHASE_DONE = "done"

PHASE_LABELS = {
    PHASE_RUNNING: "预测中",
    PHASE_AI_SUGGESTIONS_PENDING: "AI建议待确认",
    PHASE_IMPROVING: "执行改进中",
    PHASE_DONE: "已完成",
}


def get_workflow_phase_label(phase: Optional[str]) -> str:
    if not phase:
        return ""
    return PHASE_LABELS.get(phase, phase)


def _get_openai_client():
    base_url = os.environ.get("AIGC_API_URL") or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
    api_key = os.environ.get("AIGC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(base_url=base_url, api_key=api_key)
    except Exception:
        return None


def check_prerequisites_worldcup(data_src_id: int = 0) -> Dict[str, Any]:
    """AI 判断是否具备运行条件。"""
    sources = []
    try:
        from applications.worldcup.data.source_registry import list_sources
        sources = list_sources()
    except Exception:
        pass
    strategies = []
    try:
        from platform_core.strategy.registry import list_strategies
        strategies = [s.get("id") for s in list_strategies() if s.get("id")]
    except Exception:
        pass
    _base = Path(__file__).resolve().parent.parent.parent
    worldcup_config_path = _base / "applications" / "worldcup" / "config" / "config.yaml"
    data_sources_path = _base / "applications" / "worldcup" / "config" / "data_sources.yaml"
    selected_url = ""
    if data_src_id:
        try:
            ds = DataSrc.objects.get(pk=data_src_id)
            selected_url = resolve_data_src_url(ds) or ""
        except DataSrc.DoesNotExist:
            pass
    env_summary = {
        "data_src_id": data_src_id,
        "selected_full_source_url": selected_url,
        "data_sources_count": len(sources),
        "data_sources": [{"id": s.get("id"), "type": s.get("type"), "path": s.get("path")} for s in sources],
        "strategies_registered": strategies,
        "worldcup_config_exists": worldcup_config_path.exists(),
        "data_sources_config_exists": data_sources_path.exists(),
    }
    client = _get_openai_client()
    if not client:
        if not strategies:
            return {"ok": False, "error": "未注册任何策略。", "suggestion": "请加载世界杯策略并配置 AIGC_API_KEY。"}
        if not sources and not (data_src_id and selected_url):
            return {
                "ok": False,
                "error": "需要数据源。",
                "suggestion": "配置 data_sources.yaml 或在页面填写数据 URL。",
            }
        return {"ok": True}
    model = os.environ.get("AIGC_GPT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    prompt = (
        "你是预测平台的检查助手。根据以下环境信息，判断是否可以启动一轮预测。\n\n"
        "环境信息：\n%s\n\n"
        "若缺少必要条件，请说明并给出建议；若可以启动，请回复：可以启动。"
    ) % (str(env_summary),)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "只输出「可以启动」或说明缺少什么并给建议。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content or "可以启动" in content:
            return {"ok": True}
        lines = content.split("\n")
        error = lines[0].strip()
        suggestion = " ".join(l.strip() for l in lines[1:] if l.strip()) or "请根据缺少项补充后重试。"
        return {"ok": False, "error": error, "suggestion": suggestion}
    except Exception as e:
        logger.exception("Prerequisite check failed: %s", e)
        return {"ok": False, "error": "AI 检查出错。", "suggestion": "检查 AIGC_API_KEY 后重试。"}


def _get_improvement_suggestions(run_id: int) -> str:
    run = get_run(run_id)
    if not run:
        return ""
    base_url = os.environ.get("AIGC_API_URL") or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
    api_key = os.environ.get("AIGC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        return "（未配置 AIGC_API_KEY）"
    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
    except Exception as e:
        return f"（AI 初始化失败: {e}）"
    model = os.environ.get("AIGC_GPT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    prompt = (
        "根据以下实验结果，用 2～4 条中文给出改进建议。\n\n"
        "指标：%s\n参数：%s\n"
    ) % (str(run.metrics or {}), str(run.params or {}))
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "只输出简短中文建议，每条一行。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("AI suggestions failed: %s", e)
        return f"（失败: {e}）"


def _run_round_async(run_id: int, config: ExperimentConfig):
    try:
        runner = get_runner(config.data_config)
        result = runner.run(config)
        update_run_status(run_id, result.status, metrics=result.metrics, error_message=result.error_message or "")
        if result.status != "SUCCESS":
            update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})
            return
        suggestions = _get_improvement_suggestions(run_id)
        update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_AI_SUGGESTIONS_PENDING, AI_SUGGESTIONS: suggestions})
    except Exception as e:
        logger.exception("Prediction round %s failed: %s", run_id, e)
        update_run_status(run_id, "FAILED", error_message=str(e))
        update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})


def start_prediction_round(
    application: str = "worldcup",
    data_src_id: Optional[int] = None,
    data_file_version: Optional[int] = None,
    patch_batch_cts: Optional[List[int]] = None,
    incremental_update_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    启动一轮预测：
    1) 若有 incremental_update_data，先保存为 data_patch_batch + data_patch，得到新 batch 的 ct
    2) data_file_version = 传入值或当前时间
    3) patch_batch_versions = patch_batch_cts + 新 batch ct（若有），按 ct 升序
    4) 调用 load_composed_records 得到数据源
    5) 创建实验并异步执行预测
    """
    if application != "worldcup":
        return {"error": f"暂不支持应用: {application}", "suggestion": ""}
    if not data_src_id:
        return {"error": "请选择原始数据（数据源）", "suggestion": ""}

    check = check_prerequisites_worldcup(data_src_id=data_src_id)
    if not check.get("ok"):
        return {"error": check.get("error", "无法启动"), "suggestion": check.get("suggestion", "")}

    now = now_version_v()
    data_file_v = data_file_version if data_file_version is not None and data_file_version > 0 else now
    selected_cts = list(patch_batch_cts or [])

    new_batch_ct = 0
    patch_dict = incremental_update_data if isinstance(incremental_update_data, dict) else {}
    if patch_dict:
        saved = save_incremental_patches(version_v=now, patch_dict=patch_dict)
        if saved > 0:
            new_batch_ct = now

    patch_batch_versions = sorted(set(selected_cts + ([new_batch_ct] if new_batch_ct else [])))

    try:
        composed_records, snapshot_ct, patch_count = load_composed_records(
            data_src_id=data_src_id,
            data_file_version=data_file_v,
            patch_batch_versions=patch_batch_versions,
        )
        if not composed_records and snapshot_ct == 0:
            ds = DataSrc.objects.get(pk=data_src_id)
            resolved_url = (resolve_data_src_url(ds) or "").strip()
            if resolved_url:
                format_type, records = fetch_full_records(resolved_url)
                if records:
                    save_full_snapshot(version_v=now, data_src_id=data_src_id)
                    composed_records, snapshot_ct, patch_count = load_composed_records(
                        data_src_id=data_src_id,
                        data_file_version=data_file_v,
                        patch_batch_versions=patch_batch_versions,
                    )
    except Exception as e:
        logger.exception("Load composed records failed: %s", e)
        return {"error": f"加载合成数据失败: {e}", "suggestion": "请检查 data_file 与 patch_batch 是否存在。"}

    if not composed_records:
        return {"error": "当前版本缺少可用基础数据。", "suggestion": "请先保存 data_file 快照或确认 data_file_version 正确。"}

    try:
        ds = DataSrc.objects.get(pk=data_src_id)
        dest_path = (ds.raw_path or "").strip()
        source_url = resolve_data_src_url(ds) or ""
    except DataSrc.DoesNotExist:
        dest_path = ""
        source_url = ""
    composed_path = write_composed_records_file(now, composed_records, dest_path=dest_path)

    name = "世界杯预测一轮"
    strategy_id = "lightgbm_match"
    params = {
        WORKFLOW_TYPE: "worldcup_round",
        WORKFLOW_PHASE: PHASE_RUNNING,
        DATA_VERSION_V: now,
        DATA_SRC_ID: data_src_id,
        "data_file_version": data_file_v,
        "patch_batch_versions": patch_batch_versions,
        "source_url": source_url,
        UPDATE_PATCH_COUNT: patch_count,
        "composed_from_snapshot_ct": snapshot_ct,
    }
    data_config = {"path": composed_path, "format": "json", DATA_VERSION_V: now}

    run = create_run(name=name, strategy_id=strategy_id, params=params, data_config=data_config, v=now)
    config = ExperimentConfig(name=name, strategy_id=strategy_id, params=params, data_config=data_config)
    t = threading.Thread(target=_run_round_async, args=(run.id, config))
    t.daemon = True
    t.start()
    return {"id": run.id, "status": "PENDING", "data_version_v": now}


def confirm_and_apply_improvements(run_id: int) -> Dict[str, Any]:
    run = get_run(run_id)
    if not run:
        return {"error": "实验不存在"}
    params = run.params or {}
    if params.get(WORKFLOW_TYPE) != "worldcup_round":
        return {"error": "该实验不是预测流程运行"}
    if params.get(WORKFLOW_PHASE) != PHASE_AI_SUGGESTIONS_PENDING:
        return {"error": f"当前阶段不可确认: {params.get(WORKFLOW_PHASE)}"}
    update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_IMPROVING})
    update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})
    return {"id": run_id, "workflow_phase": PHASE_DONE}
