"""Strategy registration and discovery per DESIGN_SPECIFICATIONS §1.2"""
from typing import Dict, List, Optional, Type

from platform_core.strategy.base import Strategy, StrategySchema

_REGISTRY: Dict[str, Type[Strategy]] = {}
_REGISTRY_META: Dict[str, dict] = {}  # strategy_id -> { "description": str, ... }


def register_strategy(strategy_id: str, description: str = ""):
    """Decorator to register a strategy class. Optional description for UI/API."""

    def decorator(cls: Type[Strategy]):
        if not issubclass(cls, Strategy):
            raise TypeError(f"{cls} must be a subclass of Strategy")
        _REGISTRY[strategy_id] = cls
        _REGISTRY_META[strategy_id] = {"description": description or ""}
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
    """List all registered strategies with schema and description (公用：策略列表)."""
    result = []
    for sid, cls in _REGISTRY.items():
        schema = cls.get_schema()
        meta = _REGISTRY_META.get(sid) or {}
        item = {
            "id": sid,
            "name": schema.name,
            "version": schema.version,
            "params_schema": schema.params_schema,
            "description": meta.get("description", ""),
        }
        if getattr(schema, "supported_tasks", None):
            item["supported_tasks"] = schema.supported_tasks
        result.append(item)
    return result


def get_strategy_description(strategy_id: str) -> str:
    """Get description for a strategy by ID (公用：策略描述)."""
    meta = _REGISTRY_META.get(strategy_id)
    return (meta.get("description") or "") if meta else ""


def get_strategy_schema(strategy_id: str) -> Optional[StrategySchema]:
    """Get schema for a strategy by ID."""
    cls = _REGISTRY.get(strategy_id)
    if cls is None:
        return None
    return cls.get_schema()
