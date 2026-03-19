"""Fusion: odds correlation (θ) and weight derivation for WeightedEnsemble."""
from .odds_correlation import compute_odds_correlation
from .fusion_weights import (
    compute_fusion_weights_with_odds_correlation,
    get_odds_correlation_theta,
)

__all__ = [
    "compute_odds_correlation",
    "compute_fusion_weights_with_odds_correlation",
    "get_odds_correlation_theta",
]
