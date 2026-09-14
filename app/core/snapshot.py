"""Serialization of the simulator state into a displayable snapshot.

A snapshot is a JSON-serializable dictionary capturing one moment of the
simulation: what the map draws, what the timeline stores and what the agent
reads.
"""

from leosim.components import GroundStation, Satellite, User


def serialize_state(sim):
    """
    Serializes the simulator's current state into a JSON-compatible dictionary.
    """
    state = {"step": sim.scheduler.steps, "satellites": [], "ground_stations": [], "users": [], "links": []}

    # Export satellites
    for sat in Satellite.all():
        if sat.coordinates:
            state["satellites"].append(
                {
                    "id": sat.id,
                    "name": sat.name,
                    "lat": sat.coordinates[0],
                    "lon": sat.coordinates[1],
                    "alt": sat.coordinates[2],
                    "is_gateway": sat.is_gateway,
                    "active": sat.active,
                    "max_connection_range": sat.max_connection_range,
                    "process_unit": (
                        {
                            "id": sat.process_unit.id,
                            "cpu": sat.process_unit.cpu,
                            "memory": sat.process_unit.memory,
                            "storage": sat.process_unit.storage,
                        }
                        if sat.process_unit
                        else None
                    ),
                }
            )

    # Export ground stations
    for gs in GroundStation.all():
        if gs.coordinates:
            state["ground_stations"].append(
                {
                    "id": gs.id,
                    "lat": gs.coordinates[0],
                    "lon": gs.coordinates[1],
                    "alt": gs.coordinates[2] if len(gs.coordinates) > 2 else 0,
                    "max_connection_range": gs.max_connection_range,
                    "wireless_delay": gs.wireless_delay,
                    "process_units": (
                        [
                            {"id": pu.id, "cpu": pu.cpu, "memory": pu.memory, "storage": pu.storage}
                            for pu in gs.process_unit
                        ]
                        if gs.process_unit
                        else []
                    ),
                }
            )

    # Export users
    for user in User.all():
        if user.coordinates:
            state["users"].append(
                {
                    "id": user.id,
                    "lat": user.coordinates[0],
                    "lon": user.coordinates[1],
                    "alt": user.coordinates[2] if len(user.coordinates) > 2 else 0,
                    "max_connection_range": user.max_connection_range,
                    "connected_aps": (
                        [{"id": ap.id, "class": type(ap).__name__} for ap in user.network_access_points]
                        if getattr(user, "network_access_points", None)
                        else []
                    ),
                    "applications": [
                        {
                            "id": app.id,
                            "cpu_demand": app.cpu_demand,
                            "memory_demand": app.memory_demand,
                            "storage_demand": app.storage_demand,
                            "allocated_to": app.process_unit.id if getattr(app, "process_unit", None) else None,
                        }
                        for app in user.applications
                    ],
                }
            )

    # Export links
    for u, v, data in sim.topology.edges(data=True):
        if hasattr(u, "coordinates") and hasattr(v, "coordinates") and u.coordinates and v.coordinates:
            state["links"].append(
                {
                    "source": {"id": u.id, "class": type(u).__name__, "lat": u.coordinates[0], "lon": u.coordinates[1]},
                    "target": {"id": v.id, "class": type(v).__name__, "lat": v.coordinates[0], "lon": v.coordinates[1]},
                    "delay": data.get("delay", 0),
                    "bandwidth": data.get("bandwidth", 0),
                    "type": data.get("type", "static"),
                }
            )

    return state