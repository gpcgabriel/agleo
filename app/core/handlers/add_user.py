"""Handler for creating a user."""

from dataset_generator.create_components import create_user

from app.core.action_result import ActionResult


def keep_user_in_place(user):
    """Mobility model that keeps the user stationary.

    Args:
        user (User): User whose path is being extended.
    """
    user.coordinates_trace.append(user.coordinates)


def handle(session, payload):
    """Creates a stationary user at the requested position.

    Args:
        session (SimulationSession): Active simulation.
        payload (AddUserPayload): Position and range of the user.

    Returns:
        ActionResult: Confirmation of the creation.
    """
    user = create_user((payload.lat, payload.lon, 0), payload.connection_range)
    user.mobility_model = keep_user_in_place

    session.apply_infrastructure_change()

    description = f"Added User {user.id} at ({payload.lat:.4f}, {payload.lon:.4f})"
    return ActionResult(
        messages=[{"role": "system", "content": f"Action executed successfully: {description}"}],
        toast=f"Action completed: {description}",
    )
