"""Models of how users access their applications over time."""

from .dynamic_duration_access_model import DynamicDurationAccessModel
from .fixed_duration_access_model import FixedDurationAccessModel

# Naming either model: users and allocators rely only on the interface the two share.
AccessModel = FixedDurationAccessModel | DynamicDurationAccessModel

__all__ = ["AccessModel", "DynamicDurationAccessModel", "FixedDurationAccessModel"]
