"""Serialization of the simulator state into a displayable snapshot.

A snapshot is a JSON-serializable dictionary capturing one moment of the
simulation: what the map draws, what the timeline stores and what the agent
reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from leosim.components import GroundStation, Satellite, User
from leosim.geometry import ALTITUDE_INDEX, Coordinates

if TYPE_CHECKING:
    from leosim import Simulator
    from leosim.components.topology import Node

# Naming the dictionary `serialize_state` builds: JSON-ready, keyed by "step", "satellites",
# "ground_stations", "users" and "links".
Snapshot = dict[str, Any]


def serialize_state(sim: Simulator) -> Snapshot:
    """Serializes the simulator's current state into a JSON-compatible dictionary.

    Only the components with a position are drawn: a satellite the capture has
    not seen yet, for one, has none.

    Args:
        sim (Simulator): The running simulator.

    Returns:
        dict: The step and the satellites, ground stations, users and links.
    """
    return {
        "step": sim.scheduler.steps,
        "satellites": [serialize_satellite(sat, sat.coordinates) for sat in Satellite.all() if sat.coordinates],
        "ground_stations": [
            serialize_ground_station(gs, gs.coordinates) for gs in GroundStation.all() if gs.coordinates
        ],
        "users": [serialize_user(user, user.coordinates) for user in User.all() if user.coordinates],
        "links": [
            serialize_link((u, u.coordinates), (v, v.coordinates), data)
            for u, v, data in sim.topology.edges(data=True)
            if hasattr(u, "coordinates") and hasattr(v, "coordinates") and u.coordinates and v.coordinates
        ],
    }


def serialize_satellite(sat: Satellite, coordinates: Coordinates) -> dict[str, Any]:
    """Returns: dict: A satellite at the given position, with the unit it carries if any."""
    unit = sat.process_unit
    return {
        "id": sat.id,
        "name": sat.name,
        "lat": coordinates[0],
        "lon": coordinates[1],
        "alt": coordinates[2],
        "is_gateway": sat.is_gateway,
        "active": sat.active,
        "max_connection_range": sat.max_connection_range,
        "process_unit": (
            {"id": unit.id, "cpu": unit.cpu, "memory": unit.memory, "storage": unit.storage} if unit else None
        ),
    }


def serialize_ground_station(gs: GroundStation, coordinates: Coordinates) -> dict[str, Any]:
    """Returns: dict: A ground station at the given position, with its units."""
    return {
        "id": gs.id,
        "lat": coordinates[0],
        "lon": coordinates[1],
        "alt": altitude_of(coordinates),
        "max_connection_range": gs.max_connection_range,
        "wireless_delay": gs.wireless_delay,
        "process_units": [
            {"id": pu.id, "cpu": pu.cpu, "memory": pu.memory, "storage": pu.storage} for pu in gs.process_unit or []
        ],
    }


def serialize_user(user: User, coordinates: Coordinates) -> dict[str, Any]:
    """Returns: dict: A user at the given position, with its access points and its applications."""
    return {
        "id": user.id,
        "lat": coordinates[0],
        "lon": coordinates[1],
        "alt": altitude_of(coordinates),
        "max_connection_range": user.max_connection_range,
        "connected_aps": [
            {"id": ap.id, "class": type(ap).__name__} for ap in getattr(user, "network_access_points", None) or []
        ],
        "applications": [
            {
                "id": app.id,
                "cpu_demand": app.cpu_demand,
                "memory_demand": app.memory_demand,
                "storage_demand": app.storage_demand,
                "allocated_to": app.process_unit.id if app.process_unit else None,
            }
            for app in user.applications
        ],
    }


def serialize_link(
    source: tuple[Node, Coordinates], target: tuple[Node, Coordinates], data: dict[str, Any]
) -> dict[str, Any]:
    """Returns: dict: A link between two nodes, each given with its position, and its delay, bandwidth and type."""
    (u, source_position), (v, target_position) = source, target
    return {
        "source": {"id": u.id, "class": type(u).__name__, "lat": source_position[0], "lon": source_position[1]},
        "target": {"id": v.id, "class": type(v).__name__, "lat": target_position[0], "lon": target_position[1]},
        "delay": data.get("delay", 0),
        "bandwidth": data.get("bandwidth", 0),
        "type": data.get("type", "static"),
    }


def altitude_of(coordinates: Coordinates) -> float:
    """Returns: float: The altitude of a position, zero when it carries only latitude and longitude."""
    return coordinates[ALTITUDE_INDEX] if len(coordinates) > ALTITUDE_INDEX else 0


def find_default_node_position(snapshot: Snapshot | None) -> tuple[float, float] | None:
    """Finds somewhere sensible to put a node the operator did not place.

    The centre of the ground stations already in the scenario: a node dropped
    there is inside the region being simulated rather than in the ocean off
    Africa, which is where (0, 0) lands.

    Args:
        snapshot (dict): A snapshot from `serialize_state`.

    Returns:
        tuple or None: (latitude, longitude), or None when the scenario has no
        ground station to average.
    """
    stations = (snapshot or {}).get("ground_stations") or []
    placed = [station for station in stations if station.get("lat") is not None and station.get("lon") is not None]
    if not placed:
        return None

    return (
        sum(station["lat"] for station in placed) / len(placed),
        sum(station["lon"] for station in placed) / len(placed),
    )
