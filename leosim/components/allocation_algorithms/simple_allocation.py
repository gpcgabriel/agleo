from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..process_unit import ProcessUnit
from .placement import collect_requested_unserved, eligible_units

if TYPE_CHECKING:
    from ...simulator import Simulator


def is_tighter(unit: ProcessUnit, other: ProcessUnit) -> bool:
    """Returns: bool: Whether `unit` has less free CPU, memory and storage than `other`, all three at once."""
    return (
        (unit.cpu - unit.cpu_demand) < (other.cpu - other.cpu_demand)
        and (unit.memory - unit.memory_demand) < (other.memory - other.memory_demand)
        and (unit.storage - unit.storage_demand) < (other.storage - other.storage_demand)
    )


def tightest_unit(units: list[ProcessUnit]) -> ProcessUnit:
    """Returns: ProcessUnit: The first unit, replaced in order by any tighter than the one held so far."""
    selected = units[0]
    for unit in units:
        if is_tighter(unit, selected):
            selected = unit
    return selected


def simple_allocation(model: Simulator, parameters: dict[str, Any]) -> None:
    """Places each requested application on a tight eligible unit.

    The eligible units are scanned in order, keeping the first and replacing it by
    any unit with less free CPU, memory and storage, all three at once. Any
    reachable unit in the network may host an application its user's satellites
    cannot. An application that moved out of its user's reach is deprovisioned
    before anything is placed.

    Args:
        model (Simulator): The running simulator.
        parameters (dict): The algorithm's parameters, unused by this one.
    """
    to_place = collect_requested_unserved(model)

    for access_model in to_place:
        if access_model.application.available:
            access_model.application.deprovision()

    for access_model in to_place:
        application = access_model.application
        units = eligible_units(model, application, access_model.user, ProcessUnit.all())

        if not units:
            if application.available:
                application.deprovision()
            continue

        selected = tightest_unit(units)
        if selected != application.process_unit:
            application.provision(selected)
