"""Handler for advancing the simulation."""

from app.core.action_result import ActionResult


def handle(session, payload):
    """Schedules the requested steps.

    The steps are not run here: the interface loop consumes them one at a
    time so it can draw progress and offer to interrupt between them.

    Args:
        session (SimulationSession): Active simulation.
        payload (RunSimulationPayload): How many steps to run.

    Returns:
        ActionResult: No messages; the loop reports when it finishes.
    """
    session.request_steps(payload.steps)
    return ActionResult()
