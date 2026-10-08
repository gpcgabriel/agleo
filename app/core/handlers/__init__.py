"""Handler registry: one module per proposed action."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.core.actions import ActionType
from app.core.handlers import (
    add_app_to_user,
    add_nodes,
    add_process_unit,
    add_user,
    restart_simulation,
    run_full_simulation,
    run_simulation,
)

if TYPE_CHECKING:
    from app.core.action_result import ActionResult
    from app.core.session import SimulationSession

# Naming a handler's contract: it takes the session and the payload of its own action type.
Handler = Callable[["SimulationSession", Any], "ActionResult"]

HANDLERS = {
    ActionType.RUN_SIMULATION: run_simulation.handle,
    ActionType.RUN_FULL_SIMULATION: run_full_simulation.handle,
    ActionType.RESTART_SIMULATION: restart_simulation.handle,
    ActionType.ADD_PROCESS_UNIT: add_process_unit.handle,
    ActionType.ADD_NODES: add_nodes.handle,
    ActionType.ADD_USER: add_user.handle,
    ActionType.ADD_APP_TO_USER: add_app_to_user.handle,
}


def get_handler(action_type: str) -> Handler:
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
