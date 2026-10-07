"""Models that decide when a satellite fails."""

from .deterministic_failure_model import deterministic_failure_model
from .random_failure_model import random_failure_model

__all__ = ["deterministic_failure_model", "random_failure_model"]
