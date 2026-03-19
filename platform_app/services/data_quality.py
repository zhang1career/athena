"""
数据质量信息：程序执行为主、AI 生成为辅。
输出 JSON 存于 plat_exp_run.data_q。字段：label_type, sample_count, positive_class,
negative_class, balance, mean, variance, invalid_or_missing_count；多分类时增加 class_counts。

label_type 表示数据样态："binary" 二分类、"multiclass" 多分类（可扩展如 "regression"）。
二分类/多分类由调用方传入的 task 决定：
- task == "group_winner" → 二分类，标签取自 record["is_winner"] (0/1)
- 其他（如 "match_1x2"）→ 多分类，标签取自 record["result"] ("1"/"X"/"2" → 0/1/2)
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

Q_SOURCE_PROGRAM = "program"
Q_SOURCE_PROGRAM_AI = "program+ai"


def _label_from_record(record: Dict[str, Any], task: str) -> Optional[int]:
    """Extract numeric label from one record. Returns None if missing or invalid."""
    if not isinstance(record, dict):
        return None
    if task == "group_winner":
        v = record.get("is_winner")
        if v is None:
            return None
        try:
            i = int(v)
            if i in (0, 1):
                return i
        except (TypeError, ValueError):
            pass
        return None
    # match_1x2 or default: result "1" -> 0, "X" -> 1, "2" -> 2
    r = record.get("result")
    if r is None:
        return None
    s = str(r).strip().upper()
    if s == "1":
        return 0
    if s == "X":
        return 1
    if s == "2":
        return 2
    return None


def _compute_quality_metrics(
    records: List[Dict[str, Any]],
    task: str,
) -> Dict[str, Any]:
    """
    Compute data quality metrics from records.
    task: "group_winner" (binary) or e.g. "match_1x2" (multi-class).
    Returns dict with: sample_count, positive_class, negative_class, balance, mean, variance,
    invalid_or_missing_count; and class_counts when multi-class (num classes > 2).
    """
    labels: List[int] = []
    invalid_or_missing_count = 0
    for r in records or []:
        lab = _label_from_record(r, task)
        if lab is None:
            invalid_or_missing_count += 1
        else:
            labels.append(lab)

    sample_count = len(labels)
    # label_type: data regime when no valid samples use task; otherwise use observed n_classes
    def _label_type_from_task(t: str) -> str:
        return "binary" if t == "group_winner" else "multiclass"

    if sample_count == 0:
        return {
            "label_type": _label_type_from_task(task),
            "sample_count": 0,
            "positive_class": 0,
            "negative_class": 0,
            "balance": 0.0,
            "mean": 0.0,
            "variance": 0.0,
            "invalid_or_missing_count": invalid_or_missing_count,
        }

    # class counts: map class_id -> count
    from collections import Counter
    counts = Counter(labels)
    n_classes = len(counts)
    is_multiclass = n_classes > 2
    label_type = "multiclass" if is_multiclass else "binary"

    # positive_class / negative_class: for binary use class 1 vs 0; for multi-class use majority vs rest
    if is_multiclass:
        class_counts = {str(k): int(v) for k, v in sorted(counts.items())}
        majority = max(counts.values())
        rest = sample_count - majority
        positive_class = majority
        negative_class = rest
        balance = (min(counts.values()) / max(counts.values())) if counts else 0.0
    else:
        # binary: positive = 1, negative = 0
        positive_class = int(counts.get(1, 0))
        negative_class = int(counts.get(0, 0))
        balance = (min(positive_class, negative_class) / max(positive_class, negative_class)) if max(positive_class, negative_class) > 0 else 0.0
        class_counts = {}

    # mean and variance of label array (numeric)
    import numpy as np
    arr = np.array(labels, dtype=float)
    mean_val = float(np.mean(arr))
    variance_val = float(np.var(arr)) if sample_count > 1 else 0.0

    out: Dict[str, Any] = {
        "label_type": label_type,
        "sample_count": sample_count,
        "positive_class": positive_class,
        "negative_class": negative_class,
        "balance": round(balance, 6),
        "mean": round(mean_val, 6),
        "variance": round(variance_val, 6),
        "invalid_or_missing_count": invalid_or_missing_count,
    }
    if is_multiclass:
        out["class_counts"] = class_counts
    return out


def build_quality_info(
    records: List[Dict[str, Any]],
    task: str = "match_1x2",
    use_ai: bool = False,
    ai_comment_max_len: int = 200,
) -> Dict[str, Any]:
    """
    生成数据质量信息，写入 plat_exp_run.data_q。
    - task: "group_winner" (二分类) 或 "match_1x2" 等 (多分类)，用于从 record 中解析标签。
    - 固定字段: label_type, sample_count, positive_class, negative_class, balance, mean, variance, invalid_or_missing_count.
    - label_type: "binary" | "multiclass" 表示数据样态。
    - 多分类时增加 class_counts: { "0": n0, "1": n1, "2": n2 }.
    - 可选 use_ai: 在 extra 中增加 ai_comment。
    """
    q = _compute_quality_metrics(records, task)
    source = Q_SOURCE_PROGRAM

    if use_ai:
        try:
            from common.drivers.openai_driver import OpenAIDriver
            driver = OpenAIDriver()
            if driver.is_available and driver.client:
                prompt = (
                    "以下是一轮预测数据的质量指标，请用一句话（中文）给出数据质量评价或改进建议。\n\n"
                    "指标：%s\n\n只输出一句话，不要编号和多余解释。"
                ) % json.dumps(q, ensure_ascii=False, indent=0)
                resp = driver.client.chat.completions.create(
                    model=(os.environ.get("AIGC_GPT_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"),
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                )
                content = getattr(resp.choices[0].message, "content", None) if resp.choices else None
                if content and isinstance(content, str) and content.strip():
                    q.setdefault("extra", {})["ai_comment"] = content.strip()[:ai_comment_max_len]
                    source = Q_SOURCE_PROGRAM_AI
        except Exception as e:
            logger.warning("Data quality AI comment failed: %s", e)

    if "extra" not in q:
        q["extra"] = {}
    q["source"] = source
    return q
