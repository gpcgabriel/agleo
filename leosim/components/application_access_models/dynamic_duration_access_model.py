from __future__ import annotations

from typing import Any

from ...component_manager import ComponentManager
from .access_schedule import AccessSchedule


class DynamicDurationAccessModel(AccessSchedule, ComponentManager):
    """Models how a User accesses an application over time with elastic duration.

    An access ends only once the application has been provisioned for the
    required time, however long the simulation clock took to get there. The
    schedule itself lives in `AccessSchedule`.

    Attributes:
        _instances (list): List of all active model instances.
        _object_count (int): Counter for generating unique identifiers.
    """

    _instances = []
    _object_count = 0

    def new_access(
        self, start: int, duration: int, making_request: dict[str, bool], next_access: int
    ) -> dict[str, Any]:
        """Returns: dict: The record of an access whose end waits for `duration` provisioned steps."""
        return {
            "start": start,
            "provisioned_time": 0,
            "is_provisioned": False,
            "required_provisioning_time": duration,
            "end": None,  # Remains None until requirements are met
            "waiting_provisioning": 0,
            "access_time": 0,
            "connection_failure_time": 0,
            "making_request": making_request,
            "next_access": next_access,
        }

    def update_access(self) -> None:
        """Keeps the flow open while the user requests, and sets the access's end once its provisioning is met."""
        super().update_access()

        current_access = self.history[-1]

        # Closing elastically: end is set only once the provisioning quota is reached.
        if current_access["provisioned_time"] - 1 == current_access["required_provisioning_time"] and (
            self.application.available
        ):
            current_access["end"] = self.model.scheduler.steps + 1
