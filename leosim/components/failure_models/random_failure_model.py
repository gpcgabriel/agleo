from __future__ import annotations

from random import random
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..satellite import Satellite


def random_failure_model(satellite: Satellite, **parameters: Any) -> bool:
    prob = parameters.get("p", 0.1)

    first_step = parameters.get("first_error_step", 0)
    step = satellite.model.scheduler.steps + 1

    if first_step > step:
        return False

    return random() < prob
