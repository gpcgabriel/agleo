"""Handler for attaching an application to a user."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.action_result import ActionResult
from dataset_generator.create_components import attach_application_to_user
from leosim.components import Application, User

if TYPE_CHECKING:
    from app.core.actions import AddAppToUserPayload
    from app.core.session import SimulationSession


def handle(session: SimulationSession, payload: AddAppToUserPayload) -> ActionResult:
    """Creates an application and attaches it to the given user.

    Args:
        session (SimulationSession): Active simulation.
        payload (AddAppToUserPayload): Target user and application demands.

    Returns:
        ActionResult: Confirmation, or a notice if the user does not exist.
    """
    user = User.find_by("id", payload.user_id)

    if user is None:
        message = f"User {payload.user_id} not found."
        return ActionResult(messages=[{"role": "system", "content": message}], toast=message)

    # Starting the first access on the next tick. A user opens a request only
    # on the step its access begins, so an access dated from the start of the
    # run would already be under way, and the application would wait for the
    # user's next access, tens of steps later, before anyone asked for it.
    application = Application(cpu_demand=payload.cpu_demand, memory_demand=payload.memory_demand)
    attach_application_to_user(user, application, start=session.simulator.scheduler.steps + 1)
    session.apply_infrastructure_change()

    description = f"Added application (CPU={payload.cpu_demand}, Mem={payload.memory_demand}) to User {payload.user_id}"
    return ActionResult(
        messages=[{"role": "system", "content": f"Action executed successfully: {description}"}],
        toast=f"Action completed: {description}",
    )
