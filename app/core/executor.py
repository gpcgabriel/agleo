"""Execution of actions confirmed by the operator."""

from app.core.handlers import get_handler


def execute_action(session, action):
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
