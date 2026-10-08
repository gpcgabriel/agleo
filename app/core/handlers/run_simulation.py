"""Handler for advancing the simulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.action_result import ActionResult

if TYPE_CHECKING:
    from app.core.actions import RunSimulationPayload
    from app.core.session import SimulationSession


def handle(session: SimulationSession, payload: RunSimulationPayload) -> ActionResult:
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
