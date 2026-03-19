"""
AI 驱动：根据应用与策略上下文，由 LLM 生成数据需求与运行建议。

系统运行后，前端或定时任务可调用 get_recommendations(application="worldcup")，
AI 返回例如「需要最近20年的足球数据」等自然语言说明及可选的结构化需求。
"""
import json
import logging
import os
from typing import Any, Dict, Optional

from common.drivers.openai_driver import OpenAIDriver

logger = logging.getLogger(__name__)


def _build_worldcup_context() -> str:
    """构建世界杯应用的上下文说明，供 LLM 理解数据需求。"""
    strategies = []
    try:
        from platform_core.strategy.registry import list_strategies
        strategies = list_strategies()
    except Exception:
        pass
    schema_desc = """
每条比赛记录需包含：match_id, home_team, away_team, date, league, result（1=主胜/X=平/2=客胜）, home_goals, away_goals。
特征（features）为数值字典，用于模型输入；至少需要能表示主客实力的特征（如 ELO、近期表现等）。
"""
    strategies_desc = ", ".join([s.get("id", "") for s in strategies]) if strategies else "lightgbm_match, elo_baseline"
    return (
        "应用：足球世界杯胜平负预测。\n"
        "数据 schema：" + schema_desc + "\n"
        "已注册策略：" + strategies_desc + "\n"
        "请用 1～3 句话直接说明该应用需要什么样的足球数据（时间范围、联赛/赛事、必要字段或特征），并给出可选的结构化建议。"
    )


def _parse_structured_block(text: str) -> Optional[Dict[str, Any]]:
    """从 LLM 回复中解析 ```json ... ``` 块。"""
    if not text:
        return None
    start = text.find("```json")
    if start == -1:
        start = text.find("```")
    if start == -1:
        return None
    start = text.find("\n", start) + 1 if text.find("\n", start) != -1 else start + 7
    end = text.find("```", start)
    if end == -1:
        end = len(text)
    try:
        return json.loads(text[start:end].strip())
    except Exception:
        return None


def get_recommendations(application: str = "worldcup") -> Dict[str, Any]:
    """
    根据应用 ID 获取 AI 生成的数据需求与运行建议。

    返回格式：
    {
        "message": "需要最近20年的足球数据...",   # 自然语言说明
        "requirements": { ... },                  # 可选结构化需求
        "error": "..."                            # 若 LLM 不可用
    }
    """
    if application != "worldcup":
        return {
            "message": "",
            "requirements": None,
            "error": f"暂不支持应用: {application}",
        }

    context = _build_worldcup_context()
    prompt = (
        "你是一个预测平台的数据顾问。根据以下应用与数据规范，用中文简要说明该应用需要哪些数据。"
        "请直接给出结论（例如：需要最近20年的足球比赛数据，包含主客队、比分、日期及可选的 ELO 或近期表现等特征）。\n\n"
        "若方便，在回复末尾用 ```json ... ``` 输出一个结构化建议，例如：\n"
        '{"time_range_years": 20, "suggested_leagues": ["世界杯", "欧洲杯"], "required_fields": ["home_team", "away_team", "result", "date"], "suggested_features": ["elo_home", "elo_away"]}\n\n'
        "---\n" + context
    )

    driver = OpenAIDriver()
    if not driver.is_available or not driver.client:
        return {
            "message": "当前未配置 AI API，无法生成建议。请配置 AIGC_API_KEY 或 OPENAI_API_KEY 后重试。",
            "requirements": None,
            "error": "未配置 AIGC_API_KEY 或 OPENAI_API_KEY",
        }

    model = os.environ.get("AIGC_GPT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
    try:
        resp = driver.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你只输出简短、直接的数据需求说明和可选的 JSON 块。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
        )
        content = (resp.choices[0].message.content or "").strip()
        requirements = _parse_structured_block(content)
        message = content
        if requirements and "```" in content:
            message = content.split("```")[0].strip()
        return {
            "message": message,
            "requirements": requirements,
            "error": None,
        }
    except Exception as e:
        logger.exception("AI recommendations failed: %s", e)
        return {
            "message": "",
            "requirements": None,
            "error": str(e),
        }
