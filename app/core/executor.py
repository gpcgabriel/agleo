"""Execution of actions confirmed by the operator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.handlers import get_handler

if TYPE_CHECKING:
    from app.core.action_result import ActionResult
    from app.core.actions import ProposedAction
    from app.core.session import SimulationSession


def execute_action(session: SimulationSession, action: ProposedAction) -> ActionResult:
    """Applies a confirmed action.

    The executor does not know what each action does: it forwards the
    proposal to the handler registered for its type.

    Args:
        session (SimulationSession): Active simulation.
        action (ProposedAction): Proposal confirmed by the operator.

    Returns:
        ActionResult: Messages produced and, where applicable, a new session.

    Raises:
        ValueError: If the action has no registered handler.
    """
    handler = get_handler(action.action_type)
    return handler(session, action.payload)
