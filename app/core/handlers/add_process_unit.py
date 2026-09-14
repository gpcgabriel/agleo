"""Handler for attaching a process unit to an existing node."""

from leosim.components import GroundStation, Satellite

from app.core.action_result import ActionResult
from app.core.infrastructure import (
    attach_process_unit_to_ground_station,
    attach_process_unit_to_satellite,
    build_process_unit,
)


def handle(session, payload):
    """Attaches a server to the given satellite or ground station.

    Args:
        session (SimulationSession): Active simulation.
        payload (AddProcessUnitPayload): Target and server capacity.

    Returns:
        ActionResult: Confirmation, or a notice if the target does not exist.
    """
    if payload.target_type == "Satellite":
        target = Satellite.find_by("id", payload.target_id)
    else:
        target = GroundStation.find_by("id", payload.target_id)

    if target is None:
        message = f"{payload.target_type} {payload.target_id} not found."
        return ActionResult(messages=[{"role": "system", "content": message}], toast=message)

    unit = build_process_unit(payload.cpu, payload.memory)

    if payload.target_type == "Satellite":
        attach_process_unit_to_satellite(session, target, unit)
    else:
        attach_process_unit_to_ground_station(session, target, unit)

    session.apply_infrastructure_change()

    description = (
        f"Added ProcessUnit (CPU={payload.cpu}, Mem={payload.memory}) "
        f"to {payload.target_type} {payload.target_id}"
    )
    return ActionResult(
        messages=[{"role": "system", "content": f"Action executed successfully: {description}"}],
        toast=f"Action completed: {description}",
    )
