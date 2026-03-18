"""Strategy registration and discovery per DESIGN_SPECIFICATIONS §1.2"""
from typing import Dict, List, Optional, Type

from platform_core.strategy.base import Strategy, StrategySchema

_REGISTRY: Dict[str, Type[Strategy]] = {}


def register_strategy(strategy_id: str):
    """Decorator to register a strategy class."""

    def decorator(cls: Type[Strategy]):
        if not issubclass(cls, Strategy):
            raise TypeError(f"{cls} must be a subclass of Strategy")
        _REGISTRY[strategy_id] = cls
        return cls

    return decorator


def get_strategy(strategy_id: str, params: Optional[dict] = None) -> Optional[Strategy]:
    """Get a strategy instance by ID."""
    cls = _REGISTRY.get(strategy_id)
    if cls is None:
        return None
    inst = cls()
    if params:
        inst.set_params(**params)
    return inst


def list_strategies() -> List[dict]:
    """List all registered strategies with schema."""
    result = []
    for sid, cls in _REGISTRY.items():
        schema = cls.get_schema()
        item = {
            "id": sid,
            "name": schema.name,
            "version": schema.version,
            "params_schema": schema.params_schema,
        }
        if getattr(schema, "supported_tasks", None):
            item["supported_tasks"] = schema.supported_tasks
        result.append(item)
    return result


def get_strategy_schema(strategy_id: str) -> Optional[StrategySchema]:
    """Get schema for a strategy by ID."""
    cls = _REGISTRY.get(strategy_id)
    if cls is None:
        return None
    return cls.get_schema()
