"""Handler registry: one module per proposed action."""

from app.core.actions import ActionType
from app.core.handlers import (
    add_app_to_user,
    add_nodes,
    add_process_unit,
    add_user,
    restart_simulation,
    run_simulation,
)

HANDLERS = {
    ActionType.RUN_SIMULATION: run_simulation.handle,
    ActionType.RESTART_SIMULATION: restart_simulation.handle,
    ActionType.ADD_PROCESS_UNIT: add_process_unit.handle,
    ActionType.ADD_NODES: add_nodes.handle,
    ActionType.ADD_USER: add_user.handle,
    ActionType.ADD_APP_TO_USER: add_app_to_user.handle,
}


def get_handler(action_type):
    """Returns the handler for an action type.

    Args:
        action_type (str): One of the ActionType constants.

    Returns:
        Callable: A `handle(session, payload)` function.

    Raises:
        ValueError: If no handler is registered for the type.
    """
    if action_type not in HANDLERS:
        raise ValueError(f"No handler registered for action {action_type!r}.")

    return HANDLERS[action_type]
