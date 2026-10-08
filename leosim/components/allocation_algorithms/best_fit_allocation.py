from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .placement import best_fit_unit, collect_unserved, eligible_units, station_units

if TYPE_CHECKING:
    from ...simulator import Simulator


def best_fit_allocation(model: Simulator, parameters: dict[str, Any]) -> None:
    """Places each application to place on the eligible unit it fits most tightly.

    An application no unit can host is deprovisioned, if it was running.

    Args:
        model (Simulator): The running simulator.
        parameters (dict): The algorithm's parameters, with the ground station it runs for.
    """
    for access_model in collect_unserved(model):
        application = access_model.application
        units = eligible_units(model, application, access_model.user, station_units(parameters))

        if not units:
            if application.available:
                application.deprovision()
            continue

        target = best_fit_unit(application, units)
        if target != application.process_unit:
            application.provision(target)
