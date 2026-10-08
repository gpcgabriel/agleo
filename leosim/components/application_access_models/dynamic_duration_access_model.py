from __future__ import annotations

from itertools import cycle
from typing import TYPE_CHECKING, Any

import networkx as nx

from ...component_manager import ComponentManager
from ..network_flow import NetworkFlow

if TYPE_CHECKING:
    from ..application import Application
    from ..topology import Node
    from ..user import User


class DynamicDurationAccessModel(ComponentManager):
    """Models how a User accesses an application over time with elastic duration.

    This model defines patterns of provisioning requests where the end of the
    access is dynamic, occurring only after the required provisioning time
    has been effectively met, regardless of simulation clock elapsed.

    Attributes:
        _instances (list): List of all active model instances.
        _object_count (int): Counter for generating unique identifiers.
        id (int): Unique identifier for the access model.
        duration_values (list): Cycle of total required provisioning durations.
        interval_values (list): Cycle of idle intervals between accesses.
        connection_duration_values (list): Cycle of active request bursts.
        connection_interval_values (list): Cycle of idle times between bursts.
        history (list): Log of access events, metrics, and elastic timing.
        request_provisioning (bool): Flag for active provisioning intent.
        flow (NetworkFlow): The current network flow for this access.
        user (object): The User instance performing the access.
        application (object): The Application instance being accessed.
    """

    _instances = []
    _object_count = 0

    # Linking the model to its user and application: `User.connection_to_application` sets both, and
    # so does `Simulator.initialize` for a model read back from a scenario file.
    user: User
    application: Application

    def __init__(
        self,
        user: User | None = None,
        application: Application | None = None,
        start: int = 1,
        duration_values: list[int] | None = None,
        connection_duration_values: list[int] | None = None,
        interval_values: list[int] | None = None,
        connection_interval_values: list[int] | None = None,
    ) -> None:
        """Initializes a DynamicDurationAccessModel instance."""
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        self.id = self.__class__._object_count

        self.duration_values = duration_values if duration_values is not None else []
        self.interval_values = interval_values if interval_values is not None else []
        self.connection_duration_values = connection_duration_values if connection_duration_values is not None else []
        self.connection_interval_values = connection_interval_values if connection_interval_values is not None else []

        self.history: list[dict[str, Any]] = []
        self.request_provisioning = False
        self.flow: NetworkFlow | None = None

        # Leaving the links unset on the empty model the scenario loader builds; it sets them right after.
        if user is not None:
            self.user = user
        if application is not None:
            self.application = application

        if application and user:
            self.get_next_access(start)

    def export(self) -> dict[str, Any]:
        """Generates a dictionary representation for context saving."""
        component = {
            "id": self.id,
            "history": self.history,
            "request_provisioning": self.request_provisioning,
            "duration_values": self.duration_values,
            "interval_values": self.interval_values,
            "connection_duration_values": self.connection_duration_values,
            "connection_interval_values": self.connection_interval_values,
            "relationships": {
                "user": {"id": self.user.id, "class": type(self.user).__name__} if self.user else None,
                "application": (
                    {"id": self.application.id, "class": type(self.application).__name__} if self.application else None
                ),
                "flow": {"id": self.flow.id, "class": type(self.flow).__name__} if self.flow else None,
            },
        }
        return component

    def get_next_access(self, start: int) -> None:
        """Calculates the burst sequence for the next elastic access window."""
        if not hasattr(self, "duration_generator"):
            self.duration_generator = cycle(self.duration_values)

        if not hasattr(self, "connection_duration_generator"):
            self.connection_duration_generator = cycle(self.connection_duration_values)

        if not hasattr(self, "interval_generator"):
            self.interval_generator = cycle(self.interval_values)

        if not hasattr(self, "connection_interval_generator"):
            self.connection_interval_generator = cycle(self.connection_interval_values)

        interval = next(self.interval_generator)
        duration = next(self.duration_generator)

        connection_duration = next(self.connection_duration_generator)
        connection_interval = next(self.connection_interval_generator)

        making_request_times: dict[str, bool] = {}
        request_time = start
        end_time = start + duration

        while request_time < end_time:
            time_remaining = end_time - request_time
            time = min(connection_duration, time_remaining)

            for i in range(time):
                making_request_times[str(i + request_time)] = True

            request_time += time + connection_interval
            connection_duration = next(self.connection_duration_generator)
            connection_interval = next(self.connection_interval_generator)

        self.history.append(
            {
                "start": start,
                "provisioned_time": 0,
                "is_provisioned": False,
                "required_provisioning_time": duration,
                "end": None,  # Remains None until requirements are met
                "waiting_provisioning": 0,
                "access_time": 0,
                "connection_failure_time": 0,
                "making_request": making_request_times,
                "next_access": end_time + interval,
            }
        )

    def update_access(self) -> None:
        """Updates the flow based on current demand and sets elastic end time."""
        user = self.user
        app = self.application
        current_access = self.history[-1]

        if current_access["making_request"].get(str(self.model.scheduler.steps)):
            if self.flow is not None and self.flow.target != app.process_unit:
                self.flow.status = "finished"
                self.flow = None

            if app.process_unit is None:
                return

            if self.flow is None:
                connection_paths: list[list[Node]] = []
                for access_point in user.network_access_points:
                    if nx.has_path(G=self.model.topology, source=access_point, target=app.process_unit):
                        path = self.model.topology.delay_shortest_path(access_point, app.process_unit)
                        connection_paths.append(path)

                no_path: list[Node] = []
                path = min(connection_paths, key=len, default=no_path)
                self.flow = NetworkFlow(
                    start=self.model.scheduler.steps + 1,
                    source=user,
                    target=app.process_unit,
                    path=path,
                    data_to_transfer=current_access.get("data_to_transfer", 1),
                    metadata={"type": "request_response", "user": user},
                )

        # Closing elastically: end is set only once the provisioning quota is reached.
        if current_access["provisioned_time"] - 1 == current_access["required_provisioning_time"] and app.available:
            current_access["end"] = self.model.scheduler.steps + 1
