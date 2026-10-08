from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..satellite import Satellite


def deterministic_failure_model(satellite: Satellite, **parameters: Any) -> bool:
    failure_steps = parameters.get("failure_steps", [])

    first_step = parameters.get("first_error_step", 0)
    step = satellite.model.scheduler.steps + 1

    if first_step > step:
        return False

    return step in failure_steps
