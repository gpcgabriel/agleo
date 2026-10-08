from __future__ import annotations

from random import choice
from typing import TYPE_CHECKING, Any

from ..process_unit import ProcessUnit
from .placement import collect_requested_unserved, eligible_units

if TYPE_CHECKING:
    from ...simulator import Simulator


def random_allocation(model: Simulator, parameters: dict[str, Any]) -> None:
    """Places each requested application on an eligible unit drawn at random from the seeded generator.

    Any reachable unit in the network may host an application its user's satellites cannot.

    Args:
        model (Simulator): The running simulator.
        parameters (dict): The algorithm's parameters, unused by this one.
    """
    for access_model in collect_requested_unserved(model):
        application = access_model.application
        units = eligible_units(model, application, access_model.user, ProcessUnit.all())

        if not units:
            if application.available:
                application.deprovision()
            continue

        target = choice(units)
        if target != application.process_unit:
            application.provision(target)
