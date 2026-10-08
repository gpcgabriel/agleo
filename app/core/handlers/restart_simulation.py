"""Handler for restarting the simulation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.action_result import ActionResult
from app.core.bootstrap import build_simulator
from app.core.session import SimulationSession

if TYPE_CHECKING:
    from app.core.actions import RestartSimulationPayload


def handle(session: SimulationSession, payload: RestartSimulationPayload) -> ActionResult:
    """Rebuilds the simulation from scratch with the proposal's configuration.

    Args:
        session (SimulationSession): Simulation being replaced.
        payload (RestartSimulationPayload): Configuration of the restart.

    Returns:
        ActionResult: Carrying the new session.
    """
    config = payload.config
    algorithm = session.allocation_algorithm
    new_session = SimulationSession(
        build_simulator(config, allocation_algorithm=algorithm), config, allocation_algorithm=algorithm
    )

    return ActionResult(
        messages=[{"role": "system", "content": "Simulation restarted at Step 0."}],
        toast="Simulation restarted!",
        new_session=new_session,
    )
