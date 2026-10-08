from __future__ import annotations

from typing import TYPE_CHECKING, Any

import networkx as nx

from ..satellite import Satellite
from ..user import User

if TYPE_CHECKING:
    from ...simulator import Simulator
    from ..application import Application
    from ..application_access_models import AccessModel
    from ..process_unit import ProcessUnit
    from ..topology import Topology


def has_path(topology: Topology, origin: User, target: ProcessUnit) -> bool:
    for access_point in origin.network_access_points:
        if nx.has_path(G=topology, source=access_point, target=target):
            return True

    return False


def best_fit_allocation(model: Simulator, parameters: dict[str, Any]) -> None:

    def best_fit(app: Application, process_units: list[ProcessUnit]) -> ProcessUnit:
        return min(
            process_units,
            key=lambda unit: (
                (unit.cpu - app.cpu_demand) + (unit.memory - app.memory_demand) + (unit.storage - app.storage_demand)
            ),
        )

    applications_to_be_allocated: list[AccessModel] = []

    # Selecting the applications that require provisioning.
    for user in User.all():
        for access_model in user.applications_access_models:
            if not access_model.request_provisioning and access_model.application.available:
                access_model.application.deprovision()

            elif access_model.request_provisioning and not access_model.application.available:
                applications_to_be_allocated.append(access_model)
            else:
                process_unit = access_model.application.process_unit
                # Skipping what is not directly connected to a network access point.
                if (
                    not any(
                        process_unit in list(model.topology.neighbors(access_point))
                        for access_point in user.network_access_points
                    )
                    or user.network_access_points == []
                ):
                    applications_to_be_allocated.append(access_model)

    # Iterating over the provisioning demands.
    for access_model in applications_to_be_allocated:
        process_units: list[ProcessUnit] = []
        # Searching for process units directly connected to network access points.
        for access_point in access_model.user.network_access_points:
            if isinstance(access_point, Satellite) and access_point.process_unit is not None:
                process_unit = access_point.process_unit

                if process_unit.has_capacity_to_host(access_model.application) and process_unit.available:
                    process_units.append(process_unit)

        # Trying the ground network first.
        if process_units == []:
            process_units = []
            if parameters["ground_station"].process_unit:
                for unit in parameters["ground_station"].process_unit:
                    # Checking whether communication with this server is possible.
                    if (
                        unit.has_capacity_to_host(access_model.application)
                        and unit.available
                        and has_path(model.topology, access_model.user, unit)
                    ):
                        process_units.append(unit)

        if process_units == []:
            if access_model.application.available:
                access_model.application.deprovision()
            continue

        target = best_fit(app=access_model.application, process_units=process_units)

        if target != access_model.application.process_unit:
            access_model.application.provision(target)
