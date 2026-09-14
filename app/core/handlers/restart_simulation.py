"""Handler for restarting the simulation."""

from app.core.action_result import ActionResult
from app.core.bootstrap import build_simulator
from app.core.session import SimulationSession


def handle(session, payload):
    """Rebuilds the simulation from scratch with the proposal's configuration.

    Args:
        session (SimulationSession): Simulation being replaced.
        payload (RestartSimulationPayload): Configuration of the restart.

    Returns:
        ActionResult: Carrying the new session.
    """
    config = payload.config
    new_session = SimulationSession(build_simulator(config), config)

    return ActionResult(
        messages=[{"role": "system", "content": "Simulation restarted at Step 0."}],
        toast="Simulation restarted!",
        new_session=new_session,
    )
