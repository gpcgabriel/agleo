"""Allocation algorithms: each places the applications one ground station is responsible for."""

from .best_fit_allocation import best_fit_allocation
from .hybrid_allocation import hybrid_allocation
from .longest_duration_allocation import longest_duration_allocation
from .random_allocation import random_allocation
from .simple_allocation import simple_allocation

__all__ = [
    "best_fit_allocation",
    "hybrid_allocation",
    "longest_duration_allocation",
    "random_allocation",
    "simple_allocation",
]
