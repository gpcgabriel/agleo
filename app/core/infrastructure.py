"""Primitives for changing the network infrastructure.

These are the operations handlers perform on the topology: create a node,
attach a process unit, link the two. They are kept apart from the handlers so
that each handler deals with one action, not with how a satellite is born.
"""

from dataset_generator.create_components import create_link
from leosim.components import GroundStation, NetworkLink, ProcessUnit, Satellite

from app.core.catalog import CATALOG_ID_ATTRIBUTE, get_taken_catalog_ids

SATELLITE_LINK_DELAY = 1
GROUND_STATION_LINK_DELAY = 10


def build_process_unit(cpu, memory):
    """Returns: ProcessUnit: A new unit with the given capacity."""
    return ProcessUnit(cpu=cpu, memory=memory, storage=memory)


def create_satellite_from_catalog(session, coordinates):
    """Creates a satellite at the requested position, following a real trace.

    The internal id is deliberately not supplied: the class counter assigns
    the next one in sequence, matching the satellites loaded from the
    scenario. The catalog identifier is recorded separately so the same trace
    is never handed out twice.

    Args:
        session (SimulationSession): Active simulation.
        coordinates (tuple): Position (lat, lon, alt) of the satellite.

    Returns:
        Satellite: The satellite created, already added to the topology.

    Raises:
        ValueError: If no free trace exists for the requested position.
    """
    catalog_id, catalog_position = session.catalog.get_closest_satellite(
        coordinates, exclude_ids=get_taken_catalog_ids()
    )

    if catalog_id is None:
        raise ValueError("No satellite available in the traces file for this position.")

    satellite = Satellite(coordinates=coordinates, is_gateway=True)
    satellite.active = True
    satellite.coordinates_trace = session.catalog.get_coordinates_trace(catalog_id, catalog_position)
    setattr(satellite, CATALOG_ID_ATTRIBUTE, catalog_id)

    session.simulator.topology.add_node(satellite)
    return satellite


def create_ground_station(session, coordinates):
    """Returns: GroundStation: A new station at the requested position."""
    station = GroundStation(coordinates=coordinates)
    session.simulator.topology.add_node(station)
    return station


def attach_process_unit_to_satellite(session, satellite, unit):
    """Attaches a process unit to a satellite and links it into the topology."""
    unit.coordinates = satellite.coordinates
    create_link(
        unit,
        satellite,
        SATELLITE_LINK_DELAY,
        bandwidth=NetworkLink.default_bandwidth,
        topology=session.simulator.topology,
    )
    satellite.process_unit = unit
    session.simulator.topology.add_node(unit)


def attach_process_unit_to_ground_station(session, station, unit):
    """Attaches a process unit to a station and links it into the topology."""
    unit.coordinates = station.coordinates
    create_link(
        unit,
        station,
        GROUND_STATION_LINK_DELAY,
        bandwidth=NetworkLink.default_bandwidth,
        topology=session.simulator.topology,
    )
    station.connect_server(unit)
    session.simulator.topology.add_node(unit)
