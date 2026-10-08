from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..component_manager import ComponentManager

if TYPE_CHECKING:
    from .process_unit import ProcessUnit
    from .topology import Node
    from .user import User


class NetworkFlow(ComponentManager):
    """Represents specific data flows between a source and a destination.

    This class models communication between elements (e.g., user and application).
    While it currently does not allocate bandwidth, this functionality can be
    implemented using the 'flow_schedule' component in Topology.

    Attributes:
        _instances (list): List of all active NetworkFlow instances.
        _object_count (int): Counter for generating unique identifiers.
    """

    _instances = []
    _object_count = 0

    # Holding the flow's two ends, which every caller passes; only the scenario loader builds a flow without them.
    source: User
    target: ProcessUnit

    def __init__(
        self,
        id: int = 0,
        status: str = "active",
        source: User | None = None,
        target: ProcessUnit | None = None,
        start: int = 0,
        path: list[Node] | None = None,
        data_to_transfer: int = 0,
        metadata: dict[str, User | str] | None = None,
    ) -> None:
        """Initializes a NetworkFlow instance.

        Args:
            id (int): Unique identifier. Defaults to 0.
            status (str): Current flow status. Defaults to "active".
            source (object): Source component instance.
            target (object): Target component instance.
            start (int): Starting simulation step.
            path (list): List of nodes representing the network route.
            data_to_transfer (int): Total data volume to be transferred.
            metadata (dict): Additional context data for the flow.
        """

        path = path if path is not None else []

        # Adding the object to the instance list.
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        if id == 0:
            id = self.__class__._object_count
        self.id = id

        self.status = status

        if source is not None:
            self.source = source
        if target is not None:
            self.target = target

        self.start = start
        self.end = None
        self.data_to_transfer = data_to_transfer
        self.metadata = metadata if metadata is not None else {}

        self.path = path
        self.bandwidth = {}

        # Tracking the attributes that make change management easier.
        self.last_path = path.copy()
        self.last_bandwidth = {}

        for i in range(len(path) - 1):
            link = self.model.topology.link_between(path[i], path[i + 1])

            link["flows"].append(self)

            self.bandwidth[link.id] = 0
            self.last_bandwidth[link.id] = 0

    def step(self) -> None:
        """Activates the component and ensures its operation during the simulation.

        Note:
            Custom logic for flow updates can be implemented here.
        """
        pass

    def export(self) -> dict[str, Any]:
        """Generates a dictionary representation of the object for context saving.

        Returns:
            dict: The current state and configuration of the network flow.
        """
        component = {
            "id": self.id,
            "status": self.status,
            "nodes": [{"class": type(node).__name__, "id": node.id} for node in self.path],
            "path": self.path,
            "start": self.start,
            "end": self.end,
            "data_to_transfer": self.data_to_transfer,
            "bandwidth": self.bandwidth,
            "metadata": self.metadata,
        }

        return component
