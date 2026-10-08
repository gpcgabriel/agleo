from __future__ import annotations

from typing import Any

from ...component_manager import ComponentManager
from .access_schedule import AccessSchedule


class FixedDurationAccessModel(AccessSchedule, ComponentManager):
    """Models a user's access pattern to an application with fixed durations.

    Every access ends `duration` steps after it begins, however long the
    application took to be provisioned. The schedule itself lives in
    `AccessSchedule`.

    Attributes:
        _instances (list): List of all active model instances.
        _object_count (int): Counter for generating unique identifiers.
    """

    _instances = []
    _object_count = 0

    def new_access(
        self, start: int, duration: int, making_request: dict[str, bool], next_access: int
    ) -> dict[str, Any]:
        """Returns: dict: The record of an access that ends `duration` steps after it begins."""
        return {
            "start": start,
            "end": start + duration,
            "provisioned_time": 0,
            "is_provisioned": False,
            "waiting_provisioning": 0,
            "access_time": 0,
            "connection_failure_time": 0,
            "making_request": making_request,
            "next_access": next_access,
        }
