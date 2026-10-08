from __future__ import annotations

from itertools import cycle
from typing import TYPE_CHECKING, Any

from ...component_manager import ComponentManager
from ..network_flow import NetworkFlow

if TYPE_CHECKING:
    from ..application import Application
    from ..user import User


class FixedDurationAccessModel(ComponentManager):
    """Models a user's access pattern to an application with fixed durations.

    This model manages how a user requests provisioning and establishes network
    flows. It uses pre-defined cycles for provisioning duration, idle intervals,
    and specific request burst behavior (connection duration and intervals).

    Attributes:
        _instances (list): List of all active model instances.
        _object_count (int): Counter for generating unique identifiers.
        id (int): Unique identifier for the access model.
        duration_values (list): Cycle of total provisioning durations.
        interval_values (list): Cycle of idle intervals between provisioning.
        connection_duration_values (list): Cycle of active request bursts.
        connection_interval_values (list): Cycle of idle times between bursts.
        history (list): Log of all access events and metrics.
        request_provisioning (bool): Flag indicating active provisioning intent.
        flow (NetworkFlow): The current network flow associated with this access.
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
        """Initializes a FixedDurationAccessModel instance.

        Args:
            user (object): The user requesting the application.
            application (object): The application to be provisioned.
            start (int): Initial simulation step for the first access.
            duration_values (list): List of provisioning duration values.
            connection_duration_values (list): List of burst duration values.
            interval_values (list): List of intervals between accesses.
            connection_interval_values (list): List of intervals between bursts.
        """
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        self.id = self.__class__._object_count

        self.duration_values = duration_values if duration_values is not None else []
        self.interval_values = interval_values if interval_values is not None else []
        self.connection_duration_values = connection_duration_values if connection_duration_values is not None else []
        self.connection_interval_values = connection_interval_values if connection_interval_values is not None else []

        self.history = []
        self.request_provisioning = False
        self.flow = None

        # Leaving the links unset on the empty model the scenario loader builds; it sets them right after.
        if user is not None:
            self.user = user
        if application is not None:
            self.application = application

        if application and user:
            self.get_next_access(start)

    def export(self) -> dict[str, Any]:
        """Generates a dictionary representation for context saving.

        Returns:
            dict: Serialized state including cycles, history, and relationships.
        """
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
        """Calculates the steps for the next application access cycle.

        Uses cyclical generators to determine exactly at which simulation steps
        the user will perform requests within a fixed provisioning window.

        Args:
            start (int): The simulation step where this access window begins.
        """
        if not hasattr(self, "duration_generator"):
            self.duration_generator = cycle(self.duration_values)

        if not hasattr(self, "connection_duration_generator"):
            self.connection_duration_generator = cycle(self.connection_duration_values)

        if not hasattr(self, "interval_generator"):
            self.interval_generator = cycle(self.interval_values)

        if not hasattr(self, "connection_interval_generator"):
            if not self.connection_interval_values:
                raise ValueError(f"{self!r} has no connection interval values to cycle through; expected at least one.")
            self.connection_interval_generator = cycle(self.connection_interval_values)

        # Obtaining the values for this access cycle.
        interval = next(self.interval_generator)
        duration = next(self.duration_generator)

        connection_duration = next(self.connection_duration_generator)
        connection_interval = next(self.connection_interval_generator)

        making_request_times = {}
        request_time = start

        # Defining the absolute termination limit.
        end_time = start + duration

        while request_time < end_time:
            time_remaining = end_time - request_time

            # Taking the burst time as the smaller of the connection duration and the
            # time remaining.
            time = min(connection_duration, time_remaining)

            # Populating the request steps.
            for i in range(time):
                making_request_times[str(i + request_time)] = True

            # Advancing time by the connection time plus the silence interval.
            request_time += time + connection_interval

            # Preparing the values for the next iteration, if there is one.
            connection_duration = next(self.connection_duration_generator)
            connection_interval = next(self.connection_interval_generator)

        self.history.append(
            {
                "start": start,
                "end": end_time,
                "provisioned_time": 0,
                "is_provisioned": False,
                "waiting_provisioning": 0,
                "access_time": 0,
                "connection_failure_time": 0,
                "making_request": making_request_times,
                "next_access": end_time + interval,
            }
        )

    def update_access(self) -> None:
        """Updates the active network flow and connection state for the current step.

        If a request step is active, it ensures a valid NetworkFlow exists
        towards the application's current ProcessUnit.
        """
        user = self.user
        app = self.application
        current_access = self.history[-1]

        if current_access["making_request"].get(str(self.model.scheduler.steps)):
            # Finishing the outdated flow when the application has migrated.
            if self.flow is not None and self.flow.target != app.process_unit:
                self.flow.status = "finished"
                self.flow = None

            if app.process_unit is None:
                return

            if self.flow is None:
                path = self.model.topology.path_from_access_points(user, app.process_unit)

                # Creating a new dynamic network flow.
                flow = NetworkFlow(
                    start=self.model.scheduler.steps + 1,
                    source=self.user,
                    target=app.process_unit,
                    path=path,
                    data_to_transfer=current_access.get("data_to_transfer", 1),
                    metadata={"type": "request_response", "user": self.user},
                )

                self.flow = flow
