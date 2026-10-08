"""The decisions the allocation algorithms share: which applications to place, and on which units.

Each algorithm in this package composes these: one way of collecting the
applications to place, one way of finding the units that may host each, and one
way of choosing among them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...geometry import slant_range
from ..satellite import Satellite
from ..user import User

if TYPE_CHECKING:
    from collections.abc import Iterable

    from ...simulator import Simulator
    from ..application import Application
    from ..application_access_models import AccessModel
    from ..process_unit import ProcessUnit

# Naming the scenarios in which a ground station's own units take part in the placement.
SCENARIOS_WITH_GROUND_UNITS = ("terrestrial", "hybrid")


def is_next_to_access_point(model: Simulator, user: User, application: Application) -> bool:
    """Returns: bool: Whether the application runs on a unit linked directly to one of the user's access points."""
    return any(
        application.process_unit in list(model.topology.neighbors(access_point))
        for access_point in user.network_access_points
    )


def collect_requested_unserved(model: Simulator) -> list[AccessModel]:
    """Deprovisions the applications no longer requested and collects the requested ones to place.

    A requested application is collected when it is not available, or when it runs
    on a unit that none of its user's access points links to directly.

    Args:
        model (Simulator): The running simulator.

    Returns:
        list: The access models of the applications to place, in user order.
    """
    collected = []

    for user in User.all():
        for access_model in user.applications_access_models:
            application = access_model.application

            if access_model.request_provisioning:
                if not application.available or not is_next_to_access_point(model, user, application):
                    collected.append(access_model)
            elif application.available:
                application.deprovision()

    return collected


def collect_unserved(model: Simulator) -> list[AccessModel]:
    """Deprovisions the applications no longer requested and collects every application to place.

    Unlike `collect_requested_unserved`, this also collects an application no longer
    requested when it is unavailable and runs on no unit next to its user's access
    points, so the algorithms built on it place applications nobody is asking for.

    Args:
        model (Simulator): The running simulator.

    Returns:
        list: The access models of the applications to place, in user order.
    """
    collected = []

    for user in User.all():
        for access_model in user.applications_access_models:
            application = access_model.application
            requested = access_model.request_provisioning

            if not requested and application.available:
                application.deprovision()
            elif (requested and not application.available) or not is_next_to_access_point(model, user, application):
                collected.append(access_model)

    return collected


def station_units(parameters: dict[str, Any]) -> list[ProcessUnit]:
    """Returns: list: The units of the ground station the algorithm runs for, which may have none."""
    return parameters["ground_station"].process_unit or []


def satellite_units(application: Application, user: User) -> list[ProcessUnit]:
    """Returns: list: The units on the user's satellite access points that can host the application now."""
    return [
        access_point.process_unit
        for access_point in user.network_access_points
        if isinstance(access_point, Satellite)
        and access_point.process_unit is not None
        and access_point.process_unit.has_capacity_to_host(application)
        and access_point.process_unit.available
    ]


def can_host_within_reach(model: Simulator, application: Application, user: User, unit: ProcessUnit) -> bool:
    """Returns: bool: Whether the unit can host the application now and the user's access points reach it."""
    return (
        unit.has_capacity_to_host(application)
        and unit.available
        and model.topology.has_path_from_access_points(user, unit)
    )


def reachable_units(
    model: Simulator, application: Application, user: User, units: Iterable[ProcessUnit]
) -> list[ProcessUnit]:
    """Returns: list: The given units that can host the application now and that the user's access points reach."""
    return [unit for unit in units if can_host_within_reach(model, application, user, unit)]


def eligible_units(
    model: Simulator, application: Application, user: User, ground_units: Iterable[ProcessUnit]
) -> list[ProcessUnit]:
    """Finds the units that may host an application: on the user's satellites first, on the ground otherwise.

    Args:
        model (Simulator): The running simulator.
        application (Application): The application to place.
        user (User): Its user, whose access points the units are reached from.
        ground_units (Iterable): The units to fall back on when no satellite unit can host it.

    Returns:
        list: The eligible units, empty when none can host the application.
    """
    return satellite_units(application, user) or reachable_units(model, application, user, ground_units)


def best_fit_unit(application: Application, units: list[ProcessUnit]) -> ProcessUnit:
    """Returns: ProcessUnit: The unit whose total capacity exceeds the application's demand by the least."""
    return min(
        units,
        key=lambda unit: (
            (unit.cpu - application.cpu_demand)
            + (unit.memory - application.memory_demand)
            + (unit.storage - application.storage_demand)
        ),
    )


def exposure_time(user: User, satellite: Satellite) -> int:
    """Counts the steps, from the current one, during which the satellite's trace keeps it within the user's reach.

    Empty slots of the trace are skipped; the first recorded position out of reach ends the count.

    Args:
        user (User): The user to be served.
        satellite (Satellite): The satellite whose trace is followed.

    Returns:
        int: The number of steps, zero when the user has no position.
    """
    if user.coordinates is None:
        return 0

    reach = min(user.max_connection_range, satellite.max_connection_range)
    count = 0

    for coordinates in satellite.coordinates_trace[user.model.scheduler.steps :]:
        if coordinates is None:
            continue
        if slant_range(coordinates, user.coordinates) >= reach:
            break
        count += 1

    return count


def longest_duration_unit(
    model: Simulator, application: Application, user: User, parameters: dict[str, Any]
) -> ProcessUnit | None:
    """Picks the unit that keeps serving the user for longest.

    A reachable unit on the ground serves for as long as the user stays, so in the
    terrestrial and hybrid scenarios the station's first unit that can host the
    application wins. Otherwise the unit goes on the active satellite access point
    whose trace keeps it within reach for the most steps.

    Args:
        model (Simulator): The running simulator.
        application (Application): The application to place.
        user (User): Its user.
        parameters (dict): The algorithm's parameters, with the ground station and the scenario.

    Returns:
        ProcessUnit or None: The chosen unit, or None when no unit can host the application.
    """
    if parameters.get("scenario", "hybrid") in SCENARIOS_WITH_GROUND_UNITS:
        ground_unit = next(
            (unit for unit in station_units(parameters) if can_host_within_reach(model, application, user, unit)),
            None,
        )
        if ground_unit is not None:
            return ground_unit

    return longest_exposed_unit(model, application, user)


def longest_exposed_unit(model: Simulator, application: Application, user: User) -> ProcessUnit | None:
    """Returns: ProcessUnit or None: The unit on the active satellite access point that stays in reach longest."""
    best_target = None
    longest = -1

    for access_point in user.network_access_points:
        if not (model.topology.has_node(access_point) and isinstance(access_point, Satellite) and access_point.active):
            continue

        unit = access_point.process_unit
        if unit and unit.available and unit.has_capacity_to_host(application):
            duration = exposure_time(user, access_point)
            if duration > longest:
                longest = duration
                best_target = unit

    return best_target
