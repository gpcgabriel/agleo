from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, cast

import networkx as nx
from geopy.distance import geodesic

from ..component_manager import ComponentManager
from .ground_station import GroundStation
from .network_flow import NetworkFlow
from .network_link import NetworkLink
from .process_unit import ProcessUnit
from .satellite import Satellite
from .user import User

# Naming what the graph links: users reach the network through access points and are never nodes.
Node = GroundStation | Satellite | ProcessUnit
# Naming what has a position and a connection range, so its distance to another can be weighed.
Reachable = GroundStation | Satellite | User

if TYPE_CHECKING:
    # Parametrizing the graph by its nodes for the type checker alone: networkx's Graph cannot be
    # subscripted at runtime.
    NodeGraph = nx.Graph[Node]
else:
    NodeGraph = nx.Graph


class Topology(ComponentManager, NodeGraph):
    """Manages the network graph and connectivity logic of the simulation.

    Inherits from networkx.Graph to provide graph theory operations while
    integrating with the simulator's component management. It handles
    dynamic link removal, path delay calculations, and flow rerouting.

    Attributes:
        _instances (list): List of all active Topology instances.
        _object_count (int): Counter for generating unique identifiers.
        id (int): Unique identifier for the topology instance.
    """

    _instances = []
    _object_count = 0

    # Leaving the topology out of the scenario file: `Simulator.initialize` rebuilds it from the links.
    saved_in_scenario = False

    def __init__(self, obj_id: int = 0, existing_graph: nx.Graph[Node] | None = None) -> None:
        """Initializes a Topology instance.

        Args:
            obj_id (int): Unique ID. If 0, it is automatically assigned.
            existing_graph (nx.Graph, optional): An existing NetworkX graph
                to initialize the topology data.
        """
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        # Falling back to the class counter when no explicit id is given.
        if id == 0:
            obj_id = self.__class__._object_count
        self.id = obj_id

        if existing_graph is None:
            super().__init__()
        else:
            super().__init__(incoming_graph_data=existing_graph)

    def attach_link(self, link: NetworkLink) -> None:
        """Adds the edge between a link's two nodes and stores the link itself as the edge's data.

        Args:
            link (NetworkLink): The link, its `nodes` already set.
        """
        node, other = link["nodes"][0], link["nodes"][1]
        self.add_edge(node, other)

        # Replacing the edge's data dictionary with the link through `_adj`, which networkx's type
        # stubs leave out: every edge lookup then returns the link object, not a copy of its fields.
        self._adj[node][other] = link  # pyright: ignore[reportAttributeAccessIssue]
        self._adj[other][node] = link  # pyright: ignore[reportAttributeAccessIssue]

    def delay_shortest_path(self, source: Node, target: Node) -> list[Node]:
        """Returns: list: The path from one node to another with the least total link delay."""
        return nx.shortest_path(G=self, source=source, target=target, weight="delay")

    def link_between(self, node: Node, other: Node) -> NetworkLink:
        """Returns: NetworkLink: The link stored as the data of the edge between two nodes."""
        return cast(NetworkLink, self[node][other])

    def step(self) -> None:
        """Executes the topology events for the current simulation step.

        This includes removing invalid links, running management algorithms,
        updating delays, rerouting flows, and scheduling.
        """
        self.remove_invalid_connections()
        self.model.topology_management_algorithm(topology=self, **self.model.topology_management_parameters)
        self.update_delay()
        self.reroute_flows()
        self.flow_schedule()

    def update_delay(self) -> None:
        """Updates the delay attribute for all edges based on node coordinates."""
        for u, v, data in self.edges(data=True):
            link = data
            if isinstance(link, NetworkLink) and u.coordinates and v.coordinates:
                link["delay"] = link.get_delay()

    def flow_schedule(self) -> None:
        """Placeholder for bandwidth allocation or flow scheduling logic."""
        pass

    def reroute_flows(self) -> None:
        """Performs routing for flows whose current paths have become invalid.

        Checks connectivity for all active flows and finds new shortest paths
        based on delay if the existing path is broken.
        """
        for flow in NetworkFlow.all():
            if flow.status == "finished":
                continue

            path = flow.path
            need_to_reroute = False

            if path == [] or (
                flow.metadata.get("type", "default") == "request_response"
                and path[0] not in flow.source.network_access_points
            ):
                need_to_reroute = True

            else:
                for i in range(len(path) - 1):
                    if not self.has_edge(path[i], path[i + 1]):
                        need_to_reroute = True
                        break

            if need_to_reroute:
                if flow.metadata.get("type", "default") == "request_response":
                    user = flow.source
                    connection_paths = []

                    # Checking every user access point to see whether the application is
                    # reachable.
                    for access_point in user.network_access_points:
                        if nx.has_path(G=self, source=access_point, target=flow.target):
                            new_path = self.model.topology.delay_shortest_path(access_point, flow.target)
                            connection_paths.append(new_path)

                    path = min(connection_paths, key=len, default=[])

                elif nx.has_path(G=self, source=flow.source, target=flow.target):
                    path = self.delay_shortest_path(flow.source, flow.target)
                else:
                    path = []

                if path == []:
                    flow.status = "waiting"
                else:
                    flow.status = "active"

                flow.last_path = flow.path
                flow.path = path

                # Cleaning up the flows that belonged to the previous links.
                for i in range(len(flow.last_path) - 1):
                    link = self[flow.last_path[i]].get(flow.last_path[i + 1])
                    if link is None:
                        continue
                    if flow in link["flows"]:
                        link["flows"].remove(flow)

                flow.bandwidth = {}

                # Registering the flow on the new links.
                for i in range(len(path) - 1):
                    link = self.link_between(flow.path[i], flow.path[i + 1])
                    link["flows"].append(flow)
                    flow.bandwidth[link.id] = 0

    def remove_invalid_connections(self) -> None:
        """Reevaluates link existence and removes edges exceeding range limits."""
        for satellite in Satellite.all():
            link_to_removed = []

            for neighbor in self[satellite]:
                link = self.link_between(satellite, neighbor)

                if isinstance(neighbor, ProcessUnit):
                    continue

                if not Topology.within_range(satellite, neighbor) or not satellite.active:
                    if link in NetworkLink.all():
                        NetworkLink.remove(link)

                    link_to_removed.append((satellite, neighbor))

            for nodes in link_to_removed:
                self.remove_edge(nodes[0], nodes[1])

    def get_path_delay(self, path: list[Node]) -> float:
        """Calculates the total propagation delay of a given path.

        Args:
            path (list): List of nodes representing the path.

        Returns:
            float: Total delay including the initial wireless delay.
        """
        path_delay = nx.classes.function.path_weight(G=self, path=path, weight="delay")
        # Reading the wireless hop from the path's first node, which is always the user's access point.
        path_delay += cast(GroundStation | Satellite, path[0]).wireless_delay
        return path_delay

    def get_flow_delay(self, flow: NetworkFlow) -> float:
        """Calculates the current delay of a specific network flow.

        Args:
            flow (NetworkFlow): The flow instance to evaluate.

        Returns:
            float: Calculated delay. Returns infinity if the flow is waiting.
        """
        if flow.status == "waiting":
            path_delay = float("inf")
        else:
            path_delay = nx.classes.function.path_weight(G=self, path=flow.path, weight="delay")

            if isinstance(flow.source, User):
                # Reading the wireless hop from the path's first node, the user's access point.
                path_delay += cast(GroundStation | Satellite, flow.path[0]).wireless_delay
        return path_delay

    @staticmethod
    def within_range(object_1: Reachable, object_2: Reachable) -> bool:
        """Evaluates if the distance between two components is within communication range.

        Args:
            object_1 (object): First simulation component.
            object_2 (object): Second simulation component.

        Coordinates are (latitude, longitude, altitude in kilometres), so the
        vertical leg enters the slant range unscaled.

        Returns:
            bool: True if components are within the minimum range of the pair.
        """
        if object_1.coordinates is None or object_2.coordinates is None:
            return False

        distance_nodes = [object_1.max_connection_range, object_2.max_connection_range]
        ground_distance = geodesic(object_1.coordinates[:2], object_2.coordinates[:2]).kilometers
        air_distance = object_1.coordinates[2] - object_2.coordinates[2]

        return min(distance_nodes) > math.sqrt(ground_distance**2 + air_distance**2)

    @staticmethod
    def calculate_distance(object_1: Reachable, object_2: Reachable) -> float:
        """Calculates the 3D Euclidean distance between two components.

        Args:
            object_1 (object): First simulation component.
            object_2 (object): Second simulation component.

        Coordinates are (latitude, longitude, altitude in kilometres), so the
        vertical leg enters the slant range unscaled.

        Returns:
            float: Distance in kilometers. Returns infinity if coordinates are missing.
        """
        if object_1.coordinates is None or object_2.coordinates is None:
            return float("inf")

        ground_distance = geodesic(object_1.coordinates[:2], object_2.coordinates[:2]).kilometers
        air_distance = object_1.coordinates[2] - object_2.coordinates[2]

        return math.sqrt(ground_distance**2 + air_distance**2)

    def export_topology(self) -> dict[str, Any]:
        user_sat_links = []
        for user in User.all():
            for sat in Satellite.all():
                if self.has_edge(user, sat):
                    dist = self.calculate_distance(user, sat)
                    max_range = min(user.max_connection_range, sat.max_connection_range)
                    margin = round(((max_range - dist) / max_range) * 100, 1) if max_range > 0 else 0
                    user_sat_links.append(
                        {
                            "user": user.id,
                            "sat": sat.id,
                            "dist": round(dist, 1),
                            "margin_pct": margin,
                        }
                    )

        gs_sat_edges = []
        for gs in GroundStation.all():
            for sat in Satellite.all():
                if self.has_edge(gs, sat):
                    link = self.link_between(gs, sat)
                    gs_sat_edges.append(
                        {
                            "gs": gs.id,
                            "sat": sat.id,
                            "delay": link.get("delay", 0),
                        }
                    )

        link_count = sum(1 for _ in self.edges())
        active_flows = sum(1 for f in NetworkFlow.all() if f.status == "active")
        waiting_flows = sum(1 for f in NetworkFlow.all() if f.status == "waiting")

        return {
            "link_count": link_count,
            "user_sat": user_sat_links,
            "gs_sat": gs_sat_edges,
            "flows_active": active_flows,
            "flows_waiting": waiting_flows,
        }
