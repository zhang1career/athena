"""
一轮预测流程：按 data_file 版本 + data_patch_batch 版本合成数据，执行预测 → 实验结果评价。
"""
import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from common.drivers.openai_driver import OpenAIDriver
from platform_app.models import DataSrc
from platform_app.repos.experiment_repo import (
    create_run,
    get_run,
    update_run_status,
    update_run_params,
    update_run_evaluation,
)
from platform_app.services.data_src_url import resolve_data_src_url
from platform_app.services.experiment_runner import get_runner
from platform_app.services.worldcup_data_versioning import (
    fetch_full_records,
    load_composed_records,
    now_version_v,
    save_full_snapshot,
    save_incremental_patches,
    write_composed_records_file,
)
from platform_core.experiment.runner import ExperimentConfig

logger = logging.getLogger(__name__)

WORKFLOW_TYPE = "workflow_type"
WORKFLOW_PHASE = "workflow_phase"
CONFIRMED_IMPROVEMENTS_AT = "confirmed_improvements_at"
IMPROVEMENT_FOLLOW_UP_RUN_ID = "improvement_follow_up_run_id"
APPLIED_SUGGESTIONS = "applied_suggestions"
SUPPLEMENTARY = "supplementary"
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
    PHASE_AI_SUGGESTIONS_PENDING: "实验结果评价待确认",
    PHASE_IMPROVING: "执行改进中",
    PHASE_DONE: "已完成",
}


def get_workflow_phase_label(phase: Optional[str]) -> str:
    if not phase:
        return ""
    return PHASE_LABELS.get(phase, phase)


def _strategy_supports_task(strategy_id: str, task: str) -> bool:
    from platform_core.strategy.registry import get_strategy_schema
    schema = get_strategy_schema(strategy_id)
    if not schema:
        return False
    supported = getattr(schema, "supported_tasks", None) or []
    return task in supported


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
    driver = OpenAIDriver()
    if not driver.is_available or not driver.client:
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
        resp = driver.client.chat.completions.create(
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


def _extract_chat_content(resp) -> Optional[str]:
    """从 OpenAI 兼容的 chat completion 响应中提取首条 content，兼容不同实现。"""
    choices = getattr(resp, "choices", None)
    if not choices or not len(choices):
        return None
    msg = getattr(choices[0], "message", None)
    if msg is None:
        return None
    content = getattr(msg, "content", None)
    if content is not None and isinstance(content, str):
        return content
    if hasattr(msg, "text"):
        return getattr(msg, "text", None)
    if isinstance(msg, dict):
        return msg.get("content") or msg.get("text")
    return None


def _get_improvement_suggestions(run_id: int) -> str:
    run = get_run(run_id)
    if not run:
        return ""
    driver = OpenAIDriver()
    if not driver.is_available or not driver.client:
        return "（未配置 AIGC_API_KEY）"
    base_url = driver.base_url
    model = os.environ.get("AIGC_GPT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"

    # Build rich context so the AI can give concrete suggestions（字段均取自 plat_exp_run 表）
    params = run.params or {}
    metrics = run.metrics or {}
    data_config = run.data_config or {}
    strategy_schema_desc = ""
    strategy_desc = ""
    try:
        from platform_core.strategy.registry import get_strategy_schema, get_strategy_description
        schema = get_strategy_schema(run.strategy or "")
        if schema and schema.params_schema:
            strategy_schema_desc = (
                "当前策略可调参数（可据此建议调参）：%s" % (str(schema.params_schema),)
            )
        strategy_desc = get_strategy_description(run.strategy or "") or ""
    except Exception:
        pass
    strategy_display = strategy_desc if strategy_desc else (run.strategy or "（无）")

    run_description = getattr(run, "description", None) or ""
    data_q = run.data_q if isinstance(getattr(run, "data_q", None), dict) else {}

    context_parts = [
        "【实验名称】%s" % (run.name or "未命名"),
        "【实验描述】%s" % (run_description if run_description else "（无）"),
        "【应用场景】足球世界杯预测",
        "【策略】%s" % strategy_display,
        "【数据评价】%s" % json.dumps(data_q, ensure_ascii=False, indent=2),
        "【验证/测试指标】%s" % json.dumps(metrics, ensure_ascii=False, indent=2),
        "【本次运行参数】%s" % json.dumps(params, ensure_ascii=False, indent=2),
        "【数据配置摘要】path=%s, format=%s" % (
            data_config.get("path", ""),
            data_config.get("format", ""),
        ),
    ]
    if run.error_message:
        context_parts.append("【错误信息】%s" % run.error_message)
    if strategy_schema_desc:
        context_parts.append(strategy_schema_desc)

    prompt = (
        "你是一位预测实验评估顾问。根据以下实验的完整上下文，用 2～4 条简短、可操作的中文实验结果评价（每条一行）。"
        "可包括：结果解读、指标优劣、调参与数据/特征/模型方面的改进空间等。\n\n"
        "%s"
    ) % "\n\n".join(context_parts)

    messages = [
        {"role": "system", "content": "只输出 2～4 条简短中文实验结果评价，每条单独一行，不要编号外的多余解释。"},
        {"role": "user", "content": prompt},
    ]
    max_tokens_suggestions = 10_000
    logger.info(
        "AIGC API 请求参数 (run_id=%s): base_url=%s, model=%s, max_tokens=%s, messages_count=%s",
        run_id, base_url, model, max_tokens_suggestions, len(messages),
    )
    logger.info("AIGC API 请求 body.messages (run_id=%s): %s", run_id, json.dumps(messages, ensure_ascii=False, indent=2))

    try:
        resp = driver.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens_suggestions,
        )
        content = _extract_chat_content(resp)
        text = (content or "").strip()
        choices = getattr(resp, "choices", None) or []
        logger.info(
            "AIGC API 响应 (run_id=%s): choices_len=%s, extracted_content_len=%s",
            run_id, len(choices), len(text),
        )
        if choices and len(choices) > 0:
            first = choices[0]
            msg = getattr(first, "message", None)
            logger.info(
                "AIGC API 响应 choices[0] (run_id=%s): finish_reason=%s, message=%s",
                run_id,
                getattr(first, "finish_reason", None),
                repr(getattr(msg, "content", None))[:200] if msg else None,
            )
        if not text:
            logger.warning(
                "AI suggestions for run_id=%s: API returned empty content. choices_len=%s",
                run_id,
                len(choices),
            )
            return "（接口已调用但未返回评价内容，请检查 AIGC 模型名称与可用性后重试）"
        return text
    except Exception as e:
        logger.exception("AI suggestions failed: %s", e)
        return f"（失败: {e}）"


def fetch_and_save_improvement_suggestions(run_id: int) -> None:
    """
    对指定 run 调用 OpenAI 兼容接口获取实验结果评价，并写入 run.evaluation 与 workflow_phase。
    实验/Research 跑成 SUCCESS 后调用此函数即可在详情页看到评价。
    """
    evaluation_text = _get_improvement_suggestions(run_id)
    update_run_evaluation(run_id, evaluation_text)
    update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_AI_SUGGESTIONS_PENDING})


def _run_round_async(run_id: int, config: ExperimentConfig):
    try:
        # Set artifact path: artifacts/<model_name>.pkl where model_name = Train.code (fallback: run_id)
        try:
            from django.conf import settings
            resource_root = getattr(settings, "RESOURCE_ROOT", None) or os.path.join(
                Path(__file__).resolve().parent.parent.parent, "resources"
            )
            artifact_dir = os.path.join(resource_root, "artifacts")
            model_name = str(run_id)
            train_id = (config.params or {}).get("train_id")
            if train_id:
                try:
                    from platform_app.models import Train
                    train = Train.objects.filter(pk=train_id).first()
                    if train and (train.code or "").strip():
                        model_name = (train.code or "").strip()
                except Exception:
                    pass
            # Sanitize filename: only alphanumeric, underscore, hyphen
            model_name = re.sub(r"[^\w\-]", "_", model_name) or str(run_id)
            os.makedirs(artifact_dir, exist_ok=True)
            config.data_config = dict(
                config.data_config or {},
                artifact_dir=artifact_dir,
                artifact_filename=f"{model_name}.pkl",
            )
        except Exception as e:
            logger.warning("Could not set artifact path for run %s: %s", run_id, e)

        runner = get_runner(config.data_config)
        result = runner.run(config)
        update_run_status(
            run_id,
            result.status,
            metrics=result.metrics,
            error_message=result.error_message or "",
            artifacts=getattr(result, "artifacts", None),
        )
        if result.status != "SUCCESS":
            update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})
            return
        evaluation_text = _get_improvement_suggestions(run_id)
        update_run_evaluation(run_id, evaluation_text)
        update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_AI_SUGGESTIONS_PENDING})
    except Exception as e:
        logger.exception("Prediction round %s failed: %s", run_id, e)
        update_run_status(run_id, "FAILED", error_message=str(e))
        update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})


def start_prediction_round(
    application: str = "worldcup",
    data_src_id: Optional[int] = None,
    data_file_version: Optional[int] = None,
    data_file_versions: Optional[List[int]] = None,
    patch_batch_cts: Optional[List[int]] = None,
    incremental_update_data: Optional[Dict[str, Any]] = None,
    train_id: Optional[int] = None,
    quality_use_ai: bool = False,
) -> Dict[str, Any]:
    """
    启动一轮预测：
    1) 若有 incremental_update_data，先保存为 data_patch_batch + data_patch，得到新 batch 的 ct
    2) data_file_version / data_file_versions：多选时传 data_file_versions 列表，会合并多版本 records
    3) patch_batch_versions = patch_batch_cts + 新 batch ct（若有），按 ct 升序
    4) 调用 load_composed_records 得到数据源
    5) 若提供 train_id，用 Train 的 name/description 作为实验名称与 params.description，并生成数据质量 q 写入 params.q
    6) 创建实验并异步执行预测
    """
    if application != "worldcup":
        return {"error": f"暂不支持应用: {application}", "suggestion": ""}
    if not data_src_id:
        return {"error": "请选择原始数据（数据源）", "suggestion": ""}

    check = check_prerequisites_worldcup(data_src_id=data_src_id)
    if not check.get("ok"):
        return {"error": check.get("error", "无法启动"), "suggestion": check.get("suggestion", "")}

    now = now_version_v()
    use_multi_version = isinstance(data_file_versions, list) and len(data_file_versions) > 0
    if use_multi_version:
        data_file_v_list = [int(x) for x in data_file_versions if x is not None]
        data_file_v = max(data_file_v_list) if data_file_v_list else now
    else:
        data_file_v = data_file_version if data_file_version is not None and data_file_version > 0 else now
        data_file_v_list = []
    selected_cts = list(patch_batch_cts or [])

    new_batch_ct = 0
    patch_dict = incremental_update_data if isinstance(incremental_update_data, dict) else {}
    if patch_dict:
        saved = save_incremental_patches(version_v=now, patch_dict=patch_dict)
        if saved > 0:
            new_batch_ct = now

    patch_batch_versions = sorted(set(selected_cts + ([new_batch_ct] if new_batch_ct else [])))

    def _load():
        return load_composed_records(
            data_src_id=data_src_id,
            data_file_version=data_file_v if not use_multi_version else None,
            patch_batch_versions=patch_batch_versions,
            data_file_versions=data_file_v_list if use_multi_version else None,
        )

    try:
        composed_records, snapshot_ct, patch_count, envelope_meta = _load()
        if not composed_records and snapshot_ct == 0 and not use_multi_version:
            ds = DataSrc.objects.get(pk=data_src_id)
            resolved_url = (resolve_data_src_url(ds) or "").strip()
            if resolved_url:
                format_type, records = fetch_full_records(resolved_url)
                if records:
                    save_full_snapshot(version_v=now, data_src_id=data_src_id)
                    composed_records, snapshot_ct, patch_count, envelope_meta = load_composed_records(
                        data_src_id=data_src_id,
                        data_file_version=now,
                        patch_batch_versions=patch_batch_versions,
                        data_file_versions=None,
                    )
    except Exception as e:
        logger.exception("Load composed records failed: %s", e)
        return {"error": f"加载合成数据失败: {e}", "suggestion": "请检查 data_file 与 patch_batch 是否存在。"}

    if not composed_records:
        return {"error": "当前版本缺少可用基础数据。", "suggestion": "请先保存 data_file 快照或确认 data_file_version 正确。"}

    task = (envelope_meta or {}).get("task") or (envelope_meta or {}).get("data_type") or "match_1x2"
    train = None
    if train_id:
        try:
            from platform_app.models import Train
            train = Train.objects.filter(pk=train_id).first()
        except Exception:
            pass
    strategy_id = (train.strategy or "").strip() if train else ""
    if not strategy_id or not _strategy_supports_task(strategy_id, task):
        from platform_core.strategy.registry import list_strategies
        fallback = None
        for s in list_strategies():
            sid = s.get("id")
            if sid and _strategy_supports_task(sid, task):
                fallback = sid
                break
        if fallback:
            strategy_id = fallback
        else:
            ids = [sid for s in list_strategies() for sid in [s.get("id")] if sid and _strategy_supports_task(sid, task)]
            ids_preview = ", ".join(ids[:5]) if ids else "无"
            suggestion = f"请在「训练科目」中指定支持 {task} 的策略（如 {ids_preview}）。"
            return {
                "error": f"任务 {task} 无可用策略或训练科目未指定兼容策略。",
                "suggestion": suggestion,
            }

    try:
        ds = DataSrc.objects.get(pk=data_src_id)
        dest_path = (ds.raw_path or "").strip()
        source_url = resolve_data_src_url(ds) or ""
    except DataSrc.DoesNotExist:
        dest_path = ""
        source_url = ""
    composed_path = write_composed_records_file(
        now, composed_records, dest_path=dest_path, envelope_meta=envelope_meta
    )

    name = train.name if train else "世界杯预测一轮"
    description = (train.description or "") if train else ""
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
        "task": task,
        "description": description,
    }
    if data_file_v_list:
        params["data_file_versions"] = data_file_v_list
    if train_id:
        params["train_id"] = train_id
    # 数据质量：程序为主、可选 AI；写入 run.data_q，并保留 params["q"] 兼容
    try:
        from platform_app.services.data_quality import build_quality_info
        data_quality = build_quality_info(composed_records, task=task, use_ai=quality_use_ai)
        params["q"] = data_quality
    except Exception as e:
        logger.warning("Build quality_info failed: %s", e)
        data_quality = {
            "label_type": "multiclass" if task != "group_winner" else "binary",
            "sample_count": 0,
            "positive_class": 0,
            "negative_class": 0,
            "balance": 0.0,
            "mean": 0.0,
            "variance": 0.0,
            "invalid_or_missing_count": len(composed_records or []),
            "extra": {"error": str(e)},
        }
        params["q"] = data_quality

    data_config = {"path": composed_path, "format": "json", DATA_VERSION_V: now, "task": task}

    run = create_run(
        name=name,
        strategy=strategy_id,
        params=params,
        data_config=data_config,
        v=now,
        data_q=data_quality,
        description=description,
    )
    config = ExperimentConfig(name=name, strategy_id=strategy_id, params=params, data_config=data_config)
    t = threading.Thread(target=_run_round_async, args=(run.id, config))
    t.daemon = True
    t.start()
    return {"id": run.id, "status": "PENDING", "data_version_v": now}


def _suggestions_to_list(suggestions_text: Optional[str]) -> List[str]:
    """将实验结果评价文案按行拆成列表，过滤空行。"""
    if not suggestions_text or not str(suggestions_text).strip():
        return []
    return [line.strip() for line in str(suggestions_text).strip().split("\n") if line.strip()]


def apply_improvements(
    run_id: int,
    selected_indices: Optional[List[int]] = None,
    supplementary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    执行改进：记录用户勾选的建议与补充信息，调用 cursor-cli 在项目内执行改进（改代码/配置），返回过程与结果。
    使用环境变量 CURSOR_API_KEY 调用 cursor-cli（cursor-agent / agent）。
    """
    run = get_run(run_id)
    if not run:
        return {"error": "实验不存在"}
    params = run.params or {}
    if params.get(WORKFLOW_TYPE) != "worldcup_round":
        return {"error": "该实验不是预测流程运行"}
    if params.get(WORKFLOW_PHASE) != PHASE_AI_SUGGESTIONS_PENDING:
        return {"error": f"当前阶段不可执行改进: {params.get(WORKFLOW_PHASE)}"}

    evaluation_raw = getattr(run, "evaluation", None) or ""
    suggestions_list = _suggestions_to_list(evaluation_raw)
    indices = list(selected_indices or [])
    applied_suggestions = [suggestions_list[i] for i in indices if 0 <= i < len(suggestions_list)]
    supp = (supplementary or "").strip()

    process: List[str] = []
    process.append("已记录您选择的 %d 条评价项与补充信息。" % (len(applied_suggestions) + (1 if supp else 0)))
    update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_IMPROVING})

    # Build prompt for cursor-cli
    prompt_parts = [
        "你正在为 Athena 预测平台执行「改进」任务。请根据以下实验背景与用户选择的实验结果评价项，修改项目代码或配置（如策略参数、数据配置、特征等），使后续预测效果更好。",
        "",
        "【实验信息】",
        "实验名称: %s" % (run.name or "未命名"),
        "策略: %s" % (run.strategy or ""),
        "任务类型: %s" % (params.get("task") or ""),
        "指标: %s" % json.dumps(run.metrics or {}, ensure_ascii=False),
        "当前运行参数: %s" % json.dumps(params, ensure_ascii=False),
        "",
        "【用户选择的实验结果评价项】",
    ]
    for i, s in enumerate(applied_suggestions, 1):
        prompt_parts.append("%d. %s" % (i, s))
    if supp:
        prompt_parts.append("")
        prompt_parts.append("【用户补充说明】")
        prompt_parts.append(supp)
    prompt_parts.append("")
    prompt_parts.append("请在本项目仓库内直接修改代码或配置，完成后简要说明做了哪些改动。")
    prompt_text = "\n".join(prompt_parts)

    # Resolve workspace (athena project root)
    try:
        from django.conf import settings
        workspace_path = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parent.parent.parent))
    except Exception:
        workspace_path = Path(__file__).resolve().parent.parent.parent
    # Log under media so we can optionally serve it
    try:
        from django.conf import settings
        media_root = Path(getattr(settings, "MEDIA_ROOT", workspace_path / "media"))
    except Exception:
        media_root = workspace_path / "media"
    log_path = media_root / "artifacts" / "cursor_cli_logs" / ("run_%s.log" % run_id)

    from platform_app.services.cursor_cli import run_cursor_cli
    cursor_timeout = int(os.environ.get("CURSOR_CLI_TIMEOUT", "600"))
    out_cli = run_cursor_cli(
        workspace_path=workspace_path,
        prompt=prompt_text,
        log_path=log_path,
        timeout=cursor_timeout,
    )
    exit_code = out_cli.get("exit_code", -1)
    log_path_str = out_cli.get("log_path")
    process.append("已调用 cursor-cli 执行改进，退出码: %s。" % exit_code)
    if out_cli.get("error"):
        process.append("错误: %s" % out_cli["error"])
    if log_path_str:
        process.append("日志已保存: %s" % log_path_str)

    confirmed_at = datetime.now(timezone.utc).isoformat()
    update_run_params(
        run_id,
        **{
            WORKFLOW_PHASE: PHASE_DONE,
            CONFIRMED_IMPROVEMENTS_AT: confirmed_at,
            APPLIED_SUGGESTIONS: applied_suggestions,
            SUPPLEMENTARY: supp,
            "cursor_cli_exit_code": exit_code,
            "cursor_cli_log_path": log_path_str,
            "cursor_cli_completed_at": confirmed_at,
            "cursor_cli_error": out_cli.get("error"),
        },
    )
    process.append("当前实验已标记为「已完成」。")

    message = "已通过 cursor-cli 执行改进。退出码: %s。" % exit_code
    if exit_code != 0 and out_cli.get("error"):
        message += " " + out_cli["error"]

    return {
        "id": run_id,
        "workflow_phase": PHASE_DONE,
        "confirmed_at": confirmed_at,
        "process": process,
        "message": message,
        "cursor_cli_exit_code": exit_code,
        "cursor_cli_log_path": log_path_str,
    }
