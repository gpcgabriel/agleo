from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .placement import collect_unserved, longest_duration_unit

if TYPE_CHECKING:
    from ...simulator import Simulator
    from ..application_access_models import AccessModel


def remaining_time(model: Simulator, access_model: AccessModel) -> int:
    """Returns: int: How many steps the access still needs: provisioned time owed, or steps until it ends."""
    last_access = access_model.history[-1]
    if last_access.get("required_provisioning_time"):
        return last_access["required_provisioning_time"] - last_access["provisioned_time"]
    return last_access["end"] - model.scheduler.steps


def longest_duration_allocation(model: Simulator, parameters: dict[str, Any]) -> None:
    """Places each application to place on the unit that keeps serving its user for longest.

    The applications with the most time left go first, and every provisioning is
    counted in `model.provisioning_history`, by step.

    Args:
        model (Simulator): The running simulator.
        parameters (dict): The algorithm's parameters, with the ground station it runs for and the scenario.
    """
    # Keeping the counts on the model, so they survive between steps.
    if not hasattr(model, "provisioning_history"):
        model.provisioning_history = {}

    step = str(model.scheduler.steps)
    model.provisioning_history.setdefault(step, 0)

    to_place = collect_unserved(model)
    to_place.sort(key=lambda access_model: remaining_time(model, access_model), reverse=True)

    for access_model in to_place:
        application = access_model.application
        target = longest_duration_unit(model, application, access_model.user, parameters)

        if target is not None and target != application.process_unit:
            application.provision(target)
            model.provisioning_history[step] += 1
