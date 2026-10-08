from __future__ import annotations

from itertools import cycle
from typing import TYPE_CHECKING, Any, ClassVar

from ..network_flow import NetworkFlow

if TYPE_CHECKING:
    from ...simulator import Simulator
    from ..application import Application
    from ..user import User


class AccessSchedule:
    """Schedules a user's accesses to an application and keeps a flow open while it makes requests.

    Each access lasts a duration drawn in turn from `duration_values`, followed by
    an idle interval from `interval_values`; within it, the user requests in bursts
    of `connection_duration_values` steps separated by `connection_interval_values`.
    The access models mix this in ahead of ComponentManager, which stays a direct
    base of every component class: the scenario file and the metrics find the
    component classes among its direct subclasses. They differ only in when an
    access ends, which each states in `new_access`.

    Attributes:
        id (int): Unique identifier for the access model.
        duration_values (list): Cycle of access durations.
        interval_values (list): Cycle of idle intervals between accesses.
        connection_duration_values (list): Cycle of request bursts.
        connection_interval_values (list): Cycle of idle times between bursts.
        history (list): One record per access, the last one under way.
        request_provisioning (bool): Whether the application is requested now.
        flow (NetworkFlow): The flow carrying the current requests, if any.
        user (User): The user making the accesses.
        application (Application): The application accessed.
    """

    # Declaring what the component class mixing this in provides.
    model: ClassVar[Simulator]
    _instances: ClassVar[list[Any]]
    _object_count: ClassVar[int]

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
        """Initializes an access model, scheduling its first access when it has a user and an application.

        Args:
            user (User): The user requesting the application.
            application (Application): The application to be provisioned.
            start (int): Simulation step the first access begins at.
            duration_values (list): Access durations, cycled through.
            connection_duration_values (list): Request burst lengths, cycled through.
            interval_values (list): Idle intervals between accesses, cycled through.
            connection_interval_values (list): Idle times between bursts, cycled through.
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

    def new_access(
        self, start: int, duration: int, making_request: dict[str, bool], next_access: int
    ) -> dict[str, Any]:
        """Builds the record of an access about to begin, which each access model shapes by when the access ends.

        Args:
            start (int): The step the access begins at.
            duration (int): How long it lasts.
            making_request (dict): The steps, as strings, at which the user requests.
            next_access (int): The step the access after it begins at.

        Returns:
            dict: The record appended to `history`.
        """
        raise NotImplementedError(f"{type(self).__name__} does not say how its accesses end.")

    def get_next_access(self, start: int) -> None:
        """Schedules the next access: when the user requests within it, and when the one after it begins.

        Args:
            start (int): The simulation step where this access window begins.

        Raises:
            ValueError: If there are no connection intervals to cycle through.
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

        end_time = start + duration
        making_request = self.request_bursts(start, end_time)

        self.history.append(self.new_access(start, duration, making_request, end_time + interval))

    def request_bursts(self, start: int, end_time: int) -> dict[str, bool]:
        """Lays the request bursts over an access, each followed by its idle time, until the access ends.

        Args:
            start (int): The step the access begins at.
            end_time (int): The step it ends at.

        Returns:
            dict: True under each step, as a string, at which the user requests.
        """
        making_request = {}
        connection_duration = next(self.connection_duration_generator)
        connection_interval = next(self.connection_interval_generator)
        request_time = start

        while request_time < end_time:
            # Taking the burst time as the smaller of the connection duration and the
            # time remaining.
            time = min(connection_duration, end_time - request_time)

            for i in range(time):
                making_request[str(i + request_time)] = True

            # Advancing time by the connection time plus the silence interval.
            request_time += time + connection_interval

            # Preparing the values for the next iteration, if there is one.
            connection_duration = next(self.connection_duration_generator)
            connection_interval = next(self.connection_interval_generator)

        return making_request

    def update_access(self) -> None:
        """Keeps a flow open to the application's unit on every step the user makes a request.

        A flow to a unit the application left is finished first; an application
        with no unit gets no flow.
        """
        current_access = self.history[-1]
        application = self.application

        if not current_access["making_request"].get(str(self.model.scheduler.steps)):
            return

        # Finishing the outdated flow when the application has migrated.
        if self.flow is not None and self.flow.target != application.process_unit:
            self.flow.status = "finished"
            self.flow = None

        if application.process_unit is None or self.flow is not None:
            return

        self.flow = NetworkFlow(
            start=self.model.scheduler.steps + 1,
            source=self.user,
            target=application.process_unit,
            path=self.model.topology.path_from_access_points(self.user, application.process_unit),
            data_to_transfer=current_access.get("data_to_transfer", 1),
            metadata={"type": "request_response", "user": self.user},
        )
