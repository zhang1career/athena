"""Hydra config loader: platform default -> application -> CLI override."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_config_cache: Dict[str, Any] = {}


def load_config(
    application: Optional[str] = None,
    overrides: Optional[list] = None,
) -> Dict[str, Any]:
    """Load merged config. Requires hydra-core."""
    try:
        import hydra
        from omegaconf import OmegaConf
    except ImportError:
        logger.warning("hydra-core not installed, using minimal config")
        return _minimal_config(application, overrides)

    config_dir = Path(__file__).resolve().parent.parent / "config"
    with hydra.initialize_config_dir(config_dir=str(config_dir), version_base=None):
        overrides = overrides or []
        if application:
            overrides.append(f"+application={application}")
        cfg = hydra.compose(config_name="default", overrides=overrides)
        return OmegaConf.to_container(cfg, resolve=True)


def _minimal_config(application: Optional[str], overrides: Optional[list]) -> Dict[str, Any]:
    return {
        "name": "unnamed",
        "strategy_id": "sklearn_rf",
        "params": {},
        "data_config": {"train_ratio": 0.7, "val_ratio": 0.15, "n_samples": 200},
        "application": application,
    }
