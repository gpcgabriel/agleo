"""Models of how users access their applications over time."""

from .dynamic_duration_access_model import DynamicDurationAccessModel
from .fixed_duration_access_model import FixedDurationAccessModel

__all__ = ["DynamicDurationAccessModel", "FixedDurationAccessModel"]
