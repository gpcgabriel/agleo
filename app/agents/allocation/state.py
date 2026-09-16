"""Selection of the network state an allocation agent needs to see.

The full simulation state is far larger than a small local model can read,
so each ground station is shown only what bears on the applications it is
being asked to place.
"""

from math import sqrt

from geopy.distance import geodesic
from leosim.components import Application, GroundStation, ProcessUnit, Satellite, User

FUTURE_POSITIONS_SHOWN = 3


def find_pending_app_ids(all_apps):
    """Returns: list: IDs of the applications still waiting for placement."""
    return [int(key.split("_")[1]) for key, info in all_apps.items() if info.get("pending")]


def find_reachable_satellite_ids(station):
    """Finds the gateway satellites currently within reach of a station.

    Args:
        station (GroundStation): The station asking.

    Returns:
        set: IDs of the satellites in range.
    """
    reachable = set()

    if not station.coordinates:
        return reachable

    for satellite in Satellite.all():
        if not (satellite.is_gateway and satellite.active and satellite.coordinates):
            continue

        ground_distance = geodesic(station.coordinates[:2], satellite.coordinates[:2]).kilometers
        altitude_difference = (station.coordinates[2] - satellite.coordinates[2]) / 1000
        distance = sqrt(ground_distance ** 2 + altitude_difference ** 2)

        if distance < min(station.max_connection_range, satellite.max_connection_range):
            reachable.add(satellite.id)

    return reachable


def should_skip(station, pending_app_ids, reachable_satellite_ids):
    """Tells whether there is nothing for this station to decide.

    Args:
        station (GroundStation): The station asking.
        pending_app_ids (list): Applications waiting for placement.
        reachable_satellite_ids (set): Satellites currently in range.

    Returns:
        str or None: The reason to skip, or None if there is work to do.
    """
    if not pending_app_ids:
        return "no pending apps"

    if not reachable_satellite_ids and not station.process_unit:
        return "no satellites or process units in range"

    return None


def build_network_state(model, station, scenario, all_apps, pending_app_ids, reachable_satellite_ids):
    """Builds the trimmed view of the network shown to the agent.

    Args:
        model (Simulator): The running simulator.
        station (GroundStation): The station making the decision.
        scenario (str): Scenario label.
        all_apps (dict): Every exported application.
        pending_app_ids (list): Applications waiting for placement.
        reachable_satellite_ids (set): Satellites currently in range.

    Returns:
        dict: The state to serialize into the prompt.
    """
    pending_set = set(pending_app_ids)

    relevant_users = {
        user_id: info
        for user_id, info in User.export_users().items()
        if any(app_id in pending_set for app_id in info.get("pending_apps", []))
    }

    satellite_ids = set(reachable_satellite_ids)
    for info in relevant_users.values():
        for access_point in info.get("access_points", []):
            if access_point.startswith("Satellite_"):
                satellite_ids.add(int(access_point.split("_")[1]))

    satellites = {
        key: info
        for key, info in Satellite.export_satellites().items()
        if int(key.split("_")[1]) in satellite_ids
    }

    process_unit_ids = set()
    for info in satellites.values():
        unit = info.get("pu")
        if unit:
            process_unit_ids.add(unit["id"])
    for unit in station.process_unit or []:
        process_unit_ids.add(unit.id)

    # Trimmed after collecting the unit ids, which are read from these fields.
    for info in satellites.values():
        info.pop("range", None)
        info.pop("gateway", None)
        info.pop("pu", None)
        if "future" in info:
            info["future"] = info["future"][:FUTURE_POSITIONS_SHOWN]

    process_units = {
        key: info
        for key, info in ProcessUnit.export_processunits().items()
        if int(key.split("_")[1]) in process_unit_ids
    }

    applications = {
        key: info for key, info in all_apps.items() if int(key.split("_")[1]) in pending_set
    }

    topology = model.topology.export_topology()
    relevant_user_ids = {int(key.split("_")[1]) for key in relevant_users}
    topology["user_sat"] = [
        link for link in topology.get("user_sat", []) if link["user"] in relevant_user_ids
    ]
    topology["gs_sat"] = [link for link in topology.get("gs_sat", []) if link["gs"] == station.id]

    return {
        "step": model.scheduler.steps,
        "scenario": scenario,
        "ground_station": GroundStation.export_groundstations().get(f"GS_{station.id}", {}),
        "satellites": satellites,
        "users": relevant_users,
        "process_units": process_units,
        "applications": applications,
        "topology": topology,
    }


def collect_state(model, station, scenario):
    """Gathers everything the agent needs, or reports why there is nothing to do.

    Args:
        model (Simulator): The running simulator.
        station (GroundStation): The station making the decision.
        scenario (str): Scenario label.

    Returns:
        tuple: (state, pending_app_ids, skip_reason). When `skip_reason` is
        set, the other two are None.
    """
    all_apps = Application.export_applications()
    pending_app_ids = find_pending_app_ids(all_apps)
    reachable = find_reachable_satellite_ids(station)

    skip_reason = should_skip(station, pending_app_ids, reachable)
    if skip_reason:
        return None, None, skip_reason

    state = build_network_state(model, station, scenario, all_apps, pending_app_ids, reachable)
    return state, pending_app_ids, None
