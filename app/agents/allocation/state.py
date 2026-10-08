"""Selection of the network state an allocation agent needs to see.

The full simulation state is far larger than a small local model can read, so
each ground station is shown only what bears on the applications it is being
asked to place.

The narrowing happens twice. `find_servable_app_ids` decides *which*
applications a station is asked about — those whose user it can actually reach
— and `build_network_state` then trims the satellites, users, process units and
topology down to what those applications depend on. Without the first step the
second one still leaves every station answering the same network-wide question.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agents.allocation.digest import component_id
from leosim.components import Application, GroundStation, ProcessUnit, Satellite, User
from leosim.geometry import slant_range

if TYPE_CHECKING:
    from leosim import Simulator

FUTURE_POSITIONS_SHOWN = 3


def find_pending_app_ids(all_apps: dict[str, dict[str, Any]]) -> list[int]:
    """Returns: list: IDs of the applications still waiting for placement."""
    # Reading the id from keys such as "App_3", which `Application.export_applications` always writes.
    return [
        app_id for key, info in all_apps.items() if info.get("pending") and (app_id := component_id(key)) is not None
    ]


def find_reachable_satellite_ids(station: GroundStation) -> set[int]:
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

        if slant_range(station.coordinates, satellite.coordinates) < min(
            station.max_connection_range, satellite.max_connection_range
        ):
            reachable.add(satellite.id)

    return reachable


def find_servable_app_ids(
    station: GroundStation, pending_app_ids: list[int], reachable_satellite_ids: set[int]
) -> list[int]:
    """Narrows the pending applications to the ones this station could place.

    `find_pending_app_ids` answers for the whole network, so without this every
    station is asked about every application, including those belonging to
    users on the other side of the country. A station can serve an application
    when the application's user shares a satellite with it, or is attached to
    the station itself.

    Args:
        station (GroundStation): The station asking.
        pending_app_ids (list): Applications waiting for placement, network wide.
        reachable_satellite_ids (set): Satellites currently in range of the station.

    Returns:
        list: The subset of `pending_app_ids` this station could place, ordered.
    """
    pending = set(pending_app_ids)
    servable = set()

    for user in User.all():
        access_points = user.network_access_points
        if not access_points:
            continue

        reaches_user = station in access_points or any(
            isinstance(access_point, Satellite) and access_point.id in reachable_satellite_ids
            for access_point in access_points
        )
        if not reaches_user:
            continue

        for access_model in user.applications_access_models:
            if access_model.application.id in pending:
                servable.add(access_model.application.id)

    return sorted(servable)


def should_skip(station: GroundStation, pending_app_ids: list[int], reachable_satellite_ids: set[int]) -> str | None:
    """Tells whether there is nothing for this station to decide.

    Args:
        station (GroundStation): The station asking.
        pending_app_ids (list): Applications this station could place, as
            narrowed by `find_servable_app_ids`.
        reachable_satellite_ids (set): Satellites currently in range.

    Returns:
        str or None: The reason to skip, or None if there is work to do.
    """
    if not pending_app_ids:
        return "no servable pending apps"

    if not reachable_satellite_ids and not station.process_unit:
        return "no satellites or process units in range"

    return None


def build_network_state(
    model: Simulator,
    station: GroundStation,
    scenario: str,
    applications: dict[str, dict[str, Any]],
    reachable_satellite_ids: set[int],
) -> dict[str, Any]:
    """Builds the trimmed view of the network shown to the agent.

    Args:
        model (Simulator): The running simulator.
        station (GroundStation): The station making the decision.
        scenario (str): Scenario label.
        applications (dict): The exported applications this station is asked to place.
        reachable_satellite_ids (set): Satellites currently in range.

    Returns:
        dict: The state to render into the prompt, including `unit_hosts`,
        which maps each process unit to the satellite or ground station it
        sits on.
    """
    pending_set = {component_id(key) for key in applications}
    relevant_users = find_relevant_users(pending_set)

    satellite_ids: set[int | None] = set(reachable_satellite_ids)
    for info in relevant_users.values():
        satellite_ids |= {
            component_id(access_point)
            for access_point in info.get("access_points", [])
            if access_point.startswith("Satellite_")
        }

    satellites = {
        key: info for key, info in Satellite.export_satellites().items() if component_id(key) in satellite_ids
    }

    # Recording where each process unit sits while the satellites still carry
    # the link: a unit in orbit and a unit on the ground are reached by
    # different paths, and the `pu` field is dropped a few lines below.
    host_by_unit = find_unit_hosts(satellites, station)
    trim_satellites(satellites)

    return {
        "step": model.scheduler.steps,
        "scenario": scenario,
        "ground_station": GroundStation.export_groundstations().get(f"GS_{station.id}", {}),
        "satellites": satellites,
        "users": relevant_users,
        "process_units": {key: info for key, info in ProcessUnit.export_processunits().items() if key in host_by_unit},
        "unit_hosts": host_by_unit,
        "applications": applications,
        "topology": trim_topology(model, station, relevant_users),
    }


def find_relevant_users(pending_app_ids: set[int | None]) -> dict[str, dict[str, Any]]:
    """Returns: dict: The exported users with at least one of the pending applications waiting for placement."""
    return {
        user_id: info
        for user_id, info in User.export_users().items()
        if any(app_id in pending_app_ids for app_id in info.get("pending_apps", []))
    }


def find_unit_hosts(satellites: dict[str, dict[str, Any]], station: GroundStation) -> dict[str, str]:
    """Maps each process unit in reach to what it sits on: one of the satellites, or the station itself.

    Args:
        satellites (dict): The exported satellites in reach, their `pu` field still in place.
        station (GroundStation): The station making the decision.

    Returns:
        dict: "PU_<id>" to "Sat_<id>" or "GS_<id>", satellites first.
    """
    host_by_unit = {}
    for satellite_key, info in satellites.items():
        unit = info.get("pu")
        if unit:
            host_by_unit[f"PU_{unit['id']}"] = satellite_key
    for unit in station.process_unit or []:
        host_by_unit[f"PU_{unit.id}"] = f"GS_{station.id}"
    return host_by_unit


def trim_satellites(satellites: dict[str, dict[str, Any]]) -> None:
    """Drops the satellite fields the agent does not read, and keeps only the next few future positions."""
    for info in satellites.values():
        info.pop("range", None)
        info.pop("gateway", None)
        info.pop("pu", None)
        if "future" in info:
            info["future"] = info["future"][:FUTURE_POSITIONS_SHOWN]


def trim_topology(model: Simulator, station: GroundStation, relevant_users: dict[str, Any]) -> dict[str, Any]:
    """Returns: dict: The exported topology, its user links cut to the relevant users and station links to this one."""
    topology = model.topology.export_topology()
    relevant_user_ids = {component_id(key) for key in relevant_users}
    topology["user_sat"] = [link for link in topology.get("user_sat", []) if link["user"] in relevant_user_ids]
    topology["gs_sat"] = [link for link in topology.get("gs_sat", []) if link["gs"] == station.id]
    return topology


def collect_state(
    model: Simulator, station: GroundStation, scenario: str
) -> tuple[dict[str, Any] | None, list[int] | None, str | None]:
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
    reachable = find_reachable_satellite_ids(station)
    servable_app_ids = find_servable_app_ids(station, find_pending_app_ids(all_apps), reachable)

    skip_reason = should_skip(station, servable_app_ids, reachable)
    if skip_reason:
        return None, None, skip_reason

    servable = set(servable_app_ids)
    applications = {key: info for key, info in all_apps.items() if component_id(key) in servable}
    state = build_network_state(model, station, scenario, applications, reachable)
    return state, servable_app_ids, None
