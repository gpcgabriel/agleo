"""Handler for carrying out a complete simulation from a plan."""

from app.core.action_result import ActionResult
from app.core.bootstrap import build_simulator
from app.core.session import SimulationSession


def handle(session, payload):
    """Builds the plan's simulation and schedules its whole run.

    The steps are not run here. The interface loop consumes them a batch at a
    time, which is what draws progress and keeps the stop button answering,
    and it writes the report once it finds the plan finished.

    Args:
        session (SimulationSession): Simulation being replaced.
        payload (RunFullSimulationPayload): The approved plan.

    Returns:
        ActionResult: Carrying the new session with the run already scheduled.
    """
    plan = payload.plan
    algorithm = session.allocation_algorithm
    new_session = SimulationSession(
        build_simulator(plan.config, allocation_algorithm=algorithm), plan.config, allocation_algorithm=algorithm
    )
    new_session.start_plan(plan)

    return ActionResult(
        messages=[{"role": "system", "content": f"{plan.describe()}."}],
        toast="Simulation running!",
        new_session=new_session,
    )
