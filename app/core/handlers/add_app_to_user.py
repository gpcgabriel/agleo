"""Handler for attaching an application to a user."""

from dataset_generator.create_components import create_application_to_user
from leosim.components import User

from app.core.action_result import ActionResult


def handle(session, payload):
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

    create_application_to_user(user, payload.cpu_demand, payload.memory_demand)
    session.apply_infrastructure_change()

    description = (
        f"Added application (CPU={payload.cpu_demand}, Mem={payload.memory_demand}) "
        f"to User {payload.user_id}"
    )
    return ActionResult(
        messages=[{"role": "system", "content": f"Action executed successfully: {description}"}],
        toast=f"Action completed: {description}",
    )
