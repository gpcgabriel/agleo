"""Handler for creating new nodes in the topology."""

from app.core.action_result import ActionResult
from app.core.infrastructure import (
    attach_process_unit_to_ground_station,
    attach_process_unit_to_satellite,
    build_process_unit,
    create_ground_station,
    create_satellite_from_catalog,
)


def handle(session, payload):
    """Creates each requested node, along with its process unit.

    Args:
        session (SimulationSession): Active simulation.
        payload (AddNodesPayload): Nodes to create.

    Returns:
        ActionResult: Confirmation, or a notice if a node could not be created.
    """
    created = []

    for spec in payload.nodes:
        coordinates = (spec.lat, spec.lon, spec.alt)
        unit = build_process_unit(spec.cpu, spec.memory)

        try:
            if spec.node_type == "Satellite":
                satellite = create_satellite_from_catalog(session, coordinates)
                attach_process_unit_to_satellite(session, satellite, unit)
                created.append(f"{satellite}")
            else:
                station = create_ground_station(session, coordinates)
                attach_process_unit_to_ground_station(session, station, unit)
                created.append(f"{station}")
        except ValueError as error:
            # Nodes created before the failure are kept and published, so the
            # dashboard never disagrees with the engine's actual state.
            session.apply_infrastructure_change()
            message = f"Could not add {spec.node_type} at ({spec.lat:.4f}, {spec.lon:.4f}): {error}"
            return ActionResult(messages=[{"role": "system", "content": message}], toast=message)

    session.apply_infrastructure_change()

    description = f"Added {', '.join(created)}"
    return ActionResult(
        messages=[{"role": "system", "content": f"Action executed successfully: {description}"}],
        toast=f"Action completed: {description}",
    )
