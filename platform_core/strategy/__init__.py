from platform_core.strategy.base import (
    Strategy,
    PredictResult,
    StrategySchema,
)
from platform_core.strategy.registry import (
    register_strategy,
    get_strategy,
    list_strategies,
    get_strategy_schema,
    get_strategy_description,
)

# Load built-in strategies so they get registered (optional deps: skip if not installed).
# World-cup-only deployments import platform_core.strategy.base via fusion without sklearn/lightgbm.
try:
    from platform_core.strategy import sklearn_strategy  # noqa: F401
except ImportError:
    pass
try:
    from platform_core.strategy import lightgbm_strategy  # noqa: F401
except ImportError:
    pass
from platform_core.strategy import meta  # noqa: F401 - registers weighted_ensemble

__all__ = [
    "Strategy",
    "PredictResult",
    "StrategySchema",
    "register_strategy",
    "get_strategy",
    "list_strategies",
    "get_strategy_schema",
    "get_strategy_description",
]
