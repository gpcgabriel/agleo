from __future__ import annotations

from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

from ...geometry import slant_range
from ..application import Application
from .placement import best_fit_unit, eligible_units, longest_duration_unit, station_units

if TYPE_CHECKING:
    from ...simulator import Simulator
    from ..process_unit import ProcessUnit
    from ..user import User

# Naming the strategies in the order `hybrid_allocation` applies them.
STRATEGIES = ("best_fit", "longest_duration", "latency_aware", "load_balanced")


class HybridResults(TypedDict):
    """How many applications each run of `hybrid_allocation` placed, failed to place or left in place."""

    provisioned: int
    failed: int
    already: int
    details: list[dict[str, int | str | None]]
    # Counting what the model's reply left out and made up, which only the LLM allocator records.
    omitted: NotRequired[int]
    invented: NotRequired[int]


def load_ratio(unit: ProcessUnit) -> float:
    """Returns: float: The shares of CPU, memory and storage in use, summed; a resource with no capacity is full."""
    cpu_ratio = unit.cpu_demand / unit.cpu if unit.cpu > 0 else 1.0
    memory_ratio = unit.memory_demand / unit.memory if unit.memory > 0 else 1.0
    storage_ratio = unit.storage_demand / unit.storage if unit.storage > 0 else 1.0
    return cpu_ratio + memory_ratio + storage_ratio


def distance_to_user(user: User, unit: ProcessUnit) -> float:
    """Returns: float: The slant range from the user to the unit, or infinity when either has no position."""
    if user.coordinates is None or not unit.coordinates:
        return float("inf")
    return slant_range(user.coordinates, unit.coordinates)


def best_fit_choice(
    model: Simulator, application: Application, user: User, parameters: dict[str, Any]
) -> ProcessUnit | None:
    """Returns: ProcessUnit or None: The eligible unit the application fits most tightly."""
    units = eligible_units(model, application, user, station_units(parameters))
    return best_fit_unit(application, units) if units else None


def latency_aware_choice(
    model: Simulator, application: Application, user: User, parameters: dict[str, Any]
) -> ProcessUnit | None:
    """Returns: ProcessUnit or None: The eligible unit nearest the user."""
    units = eligible_units(model, application, user, station_units(parameters))
    return min(units, key=lambda unit: distance_to_user(user, unit)) if units else None


def load_balanced_choice(
    model: Simulator, application: Application, user: User, parameters: dict[str, Any]
) -> ProcessUnit | None:
    """Returns: ProcessUnit or None: The eligible unit with the lowest share of its resources in use."""
    units = eligible_units(model, application, user, station_units(parameters))
    return min(units, key=load_ratio) if units else None


# Mapping each strategy to how it chooses a unit for one application.
CHOICES = {
    "best_fit": best_fit_choice,
    "longest_duration": longest_duration_unit,
    "latency_aware": latency_aware_choice,
    "load_balanced": load_balanced_choice,
}


def allocate_single_app(
    model: Simulator, application: Application, user: User, parameters: dict[str, Any], strategy: str
) -> str:
    """Places one application by one strategy.

    Args:
        model (Simulator): The running simulator.
        application (Application): The application to place.
        user (User): Its user.
        parameters (dict): The algorithm's parameters, with the ground station it runs for.
        strategy (str): One of `STRATEGIES`.

    Returns:
        str: "provisioned", "already_provisioned", "failed_no_capacity" or "unknown_strategy".
    """
    choose = CHOICES.get(strategy)
    if choose is None:
        return "unknown_strategy"

    target = choose(model, application, user, parameters)
    if target is None:
        return "failed_no_capacity"
    if target == application.process_unit:
        return "already_provisioned"

    application.provision(target)
    return "provisioned"


def hybrid_allocation(
    model: Simulator, parameters: dict[str, Any], app_ids_by_strategy: dict[str, list[int]]
) -> HybridResults:
    """Places each listed application by the strategy it is listed under, strategy by strategy in `STRATEGIES` order.

    Args:
        model (Simulator): The running simulator.
        parameters (dict): The algorithm's parameters, with the ground station it runs for.
        app_ids_by_strategy (dict): Application ids under the strategy that places them; a strategy
            left out places nothing.

    Returns:
        dict: How many were provisioned, failed or already in place, with one detail row per application.
    """
    results: HybridResults = {"provisioned": 0, "failed": 0, "already": 0, "details": []}

    for strategy in STRATEGIES:
        for app_id in app_ids_by_strategy.get(strategy, []):
            application = Application.find_by("id", app_id)
            if not application or not application.user:
                continue

            result = allocate_single_app(model, application, application.user, parameters, strategy)
            results["details"].append({"app": app_id, "strategy": strategy, "result": result})
            if result == "provisioned":
                results["provisioned"] += 1
            elif result == "failed_no_capacity":
                results["failed"] += 1
            else:
                results["already"] += 1

    return results
