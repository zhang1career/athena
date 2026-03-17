"""
一轮预测流程：启动前由 AI 判断是否缺少数据/配置等；通过则执行：获取数据 → 运行预测 → 对比结果 → AI 给出改进意见 → 人工确认后执行改进。

流程状态通过 experiment.params 存储：workflow_type, workflow_phase, ai_suggestions。
"""
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from common.snowflake import get_snowflake_id
from platform_app.repos.experiment_repo import (
    create_run,
    get_run,
    update_run_status,
    update_run_params,
)
from platform_core.experiment.runner import ExperimentConfig
from platform_app.services.experiment_runner import get_runner

logger = logging.getLogger(__name__)

WORKFLOW_TYPE = "workflow_type"
WORKFLOW_PHASE = "workflow_phase"
AI_SUGGESTIONS = "ai_suggestions"

# 流程阶段
PHASE_RUNNING = "running"                    # 获取数据 + 预测 + 对比中
PHASE_AI_SUGGESTIONS_PENDING = "ai_suggestions_pending"  # AI 已给出建议，待人工确认
PHASE_IMPROVING = "improving"                # 已确认，执行改进中
PHASE_DONE = "done"                          # 本轮结束

# 阶段展示文案（实验列表用）
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
    """OpenAI 兼容 API 客户端。"""
    base_url = os.environ.get("AIGC_API_URL") or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
    api_key = os.environ.get("AIGC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(base_url=base_url, api_key=api_key)
    except Exception:
        return None


def check_prerequisites_worldcup() -> Dict[str, Any]:
    """
    由 AI 根据当前环境判断是否可以启动一轮预测；若缺少数据、配置等则返回 error + suggestion。
    返回 {"ok": True} 或 {"ok": False, "error": "...", "suggestion": "..."}。
    """
    # 收集环境信息
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
    env_summary = {
        "data_sources_count": len(sources),
        "data_sources": [{"id": s.get("id"), "type": s.get("type"), "path": s.get("path")} for s in sources],
        "strategies_registered": strategies,
        "worldcup_config_exists": worldcup_config_path.exists(),
        "data_sources_config_exists": data_sources_path.exists(),
    }
    # 若未配置 AI，做简单规则检查并返回
    client = _get_openai_client()
    if not client:
        if not strategies:
            return {"ok": False, "error": "未注册任何策略，无法运行预测。", "suggestion": "请确保已加载世界杯策略（如 lightgbm_match、elo_baseline）并配置 AIGC_API_KEY 以启用 AI 检查。"}
        if not env_summary["data_sources_config_exists"] and env_summary["data_sources_count"] == 0:
            return {"ok": False, "error": "未发现数据源配置。", "suggestion": "在 applications/worldcup/config/data_sources.yaml 中配置至少一个数据源（如 local_csv 的 path），或创建该文件。"}
        # 规则上允许用 mock 数据跑
        return {"ok": True}
    model = os.environ.get("AIGC_GPT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    prompt = (
        "你是预测平台的检查助手。根据以下「世界杯预测」应用的环境信息，判断是否可以启动一轮预测（即能否获取数据、运行预测算法）。\n\n"
        "环境信息：\n%s\n\n"
        "若缺少必要条件（例如：没有数据源、没有可用的数据文件路径、未注册策略、缺少配置等），请用一两句话说明「缺少什么」，并在下一段用「建议：」开头给出 1～3 条具体改进建议。\n"
        "若可以启动（例如：有数据源或可回退到模拟数据、策略已注册），请只回复：可以启动。"
    ) % (str(env_summary),)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你只输出要么「可以启动」，要么先说明缺少什么再给出「建议：」开头的几条建议。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=400,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            return {"ok": True}
        if "可以启动" in content or "可以" == content[:2]:
            return {"ok": True}
        lines = content.split("\n")
        error = lines[0].strip()
        suggestion = ""
        for i, line in enumerate(lines[1:], 1):
            line = line.strip()
            if line.startswith("建议：") or line.startswith("建议:"):
                suggestion = line.split("：", 1)[-1].split(":", 1)[-1].strip()
                if i + 1 < len(lines):
                    suggestion += " " + " ".join(l.strip() for l in lines[i + 1:] if l.strip())
                break
            if line:
                suggestion = line
                break
        if not suggestion:
            suggestion = "请根据上述缺少项补充数据或配置后重试。"
        return {"ok": False, "error": error, "suggestion": suggestion}
    except Exception as e:
        logger.exception("Prerequisite check failed: %s", e)
        return {"ok": False, "error": "AI 检查前置条件时出错。", "suggestion": "请检查 AIGC_API_KEY 与网络，或稍后重试。"}


def _get_improvement_suggestions(run_id: int) -> str:
    """根据实验指标与参数，调用 LLM 生成改进建议。"""
    run = get_run(run_id)
    if not run:
        return ""
    base_url = os.environ.get("AIGC_API_URL") or os.environ.get("OPENAI_API_BASE") or "https://api.openai.com/v1"
    api_key = os.environ.get("AIGC_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not api_key:
        return "（未配置 AI API，无法生成改进建议。请配置 AIGC_API_KEY 后重试。）"
    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=api_key)
    except Exception as e:
        return f"（AI 客户端初始化失败: {e}）"
    model = os.environ.get("AIGC_GPT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    prompt = (
        "你是预测平台的改进顾问。根据以下一次足球胜平负预测实验的结果，用 2～4 条中文给出改进建议，"
        "可涉及：数据（时间范围、联赛、特征）、策略参数、或模型选择。\n\n"
        "实验指标：%s\n"
        "策略参数：%s\n"
        "请直接输出建议，不要代码块。"
    ) % (
        str(run.metrics or {}),
        str(run.params or {}),
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你只输出简短的中文改进建议，每条一行。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logger.exception("AI improvement suggestions failed: %s", e)
        return f"（生成建议失败: {e}）"


def _run_round_async(run_id: int, config: ExperimentConfig):
    """异步执行：跑实验 → 成功后请求 AI 建议 → 写入 run.params。"""
    try:
        runner = get_runner(config.data_config)
        result = runner.run(config)
        update_run_status(
            run_id,
            result.status,
            metrics=result.metrics,
            error_message=result.error_message or "",
        )
        if result.status != "SUCCESS":
            update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})
            return
        suggestions = _get_improvement_suggestions(run_id)
        update_run_params(
            run_id,
            **{WORKFLOW_PHASE: PHASE_AI_SUGGESTIONS_PENDING, AI_SUGGESTIONS: suggestions},
        )
    except Exception as e:
        logger.exception("Prediction round run_id=%s failed: %s", run_id, e)
        update_run_status(run_id, "FAILED", error_message=str(e))
        update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})


def start_prediction_round(application: str = "worldcup") -> Dict[str, Any]:
    """
    启动一轮预测流程：先由 AI 判断是否缺少数据/配置等；通过则创建一条带 workflow 的实验并异步执行 预测 → AI 建议。
    返回 {"run_id": ..., "status": "PENDING"} 或 {"error": "...", "suggestion": "..."}。
    """
    if application != "worldcup":
        return {"error": f"暂不支持应用: {application}", "suggestion": ""}

    check = check_prerequisites_worldcup()
    if not check.get("ok"):
        return {
            "error": check.get("error", "无法启动一轮预测"),
            "suggestion": check.get("suggestion", ""),
        }

    run_id = get_snowflake_id()
    name = "世界杯预测一轮"
    strategy_id = "lightgbm_match"
    params = {
        WORKFLOW_TYPE: "worldcup_round",
        WORKFLOW_PHASE: PHASE_RUNNING,
    }
    data_config = {}  # 使用默认或从 config 读；暂无数据时 runner 可能用 mock
    create_run(
        run_id=run_id,
        name=name,
        strategy_id=strategy_id,
        params=params,
        data_config=data_config,
    )
    config = ExperimentConfig(
        name=name,
        strategy_id=strategy_id,
        params=params,
        data_config=data_config,
    )
    t = threading.Thread(target=_run_round_async, args=(run_id, config))
    t.daemon = True
    t.start()
    return {"run_id": run_id, "status": "PENDING"}


def confirm_and_apply_improvements(run_id: int) -> Dict[str, Any]:
    """
    人工确认后执行改进：将阶段设为 improving，再设为 done。
    当前仅做状态推进；后续可在此创建子实验或调整参数。
    """
    run = get_run(run_id)
    if not run:
        return {"error": "实验不存在"}
    params = run.params or {}
    if params.get(WORKFLOW_TYPE) != "worldcup_round":
        return {"error": "该实验不是预测流程运行"}
    phase = params.get(WORKFLOW_PHASE)
    if phase != PHASE_AI_SUGGESTIONS_PENDING:
        return {"error": f"当前阶段不可确认（阶段: {phase}）"}
    update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_IMPROVING})
    # 执行改进：此处可创建子实验、更新策略参数等；简化实现仅标记完成
    update_run_params(run_id, **{WORKFLOW_PHASE: PHASE_DONE})
    return {"run_id": run_id, "workflow_phase": PHASE_DONE}
