"""Strategy base classes per DESIGN_SPECIFICATIONS §1"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class PredictResult:
    """Prediction result, serializable and observable."""
    predictions: Any
    proba: Optional[Any] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class StrategySchema:
    """Strategy metadata for AI discovery."""
    name: str
    version: str
    params_schema: Dict[str, dict]  # JSON Schema style


class Strategy(ABC):
    """Unified strategy interface."""

    @abstractmethod
    def fit(self, X, y, **kwargs) -> None:
        """Train the strategy."""
        pass

    @abstractmethod
    def predict(self, X, **kwargs) -> PredictResult:
        """Make predictions."""
        pass

    def get_params(self) -> dict:
        """Return strategy parameters."""
        return {}

    def set_params(self, **params) -> None:
        """Update strategy parameters."""
        pass

    @classmethod
    @abstractmethod
    def get_schema(cls) -> StrategySchema:
        """Return parameter schema for AI discovery."""
        pass
