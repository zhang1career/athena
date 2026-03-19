"""Shared experiment runner factory for API and prediction round pipeline."""
from platform_core.experiment.runner import LocalRunner


def _resolve_data_loader(data_config: dict):
    """Use worldcup loader if path given, else mock."""
    if data_config.get("path") or data_config.get("data_path"):
        try:
            from applications.worldcup.data.loader import worldcup_data_loader
            return lambda cfg: worldcup_data_loader(cfg)
        except ImportError:
            pass
    # Mock loader
    def _mock(cfg):
        import numpy as np
        n = cfg.get("n_samples", 200)
        X = np.random.randn(n, 5)
        y = (X[:, 0] > 0).astype(int)
        t1, t2 = int(n * 0.7), int(n * 0.85)
        return X[:t1], y[:t1], X[t1:t2], y[t1:t2], X[t2:], y[t2:]
    return _mock


def get_runner(data_config: dict):
    loader = _resolve_data_loader(data_config or {})
    return LocalRunner(loader)
