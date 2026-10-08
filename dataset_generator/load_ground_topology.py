from typing import cast

import networkx as nx

from leosim.components import GroundStation, NetworkLink, Topology
from leosim.components.topology import Node

from .create_components import MAX_RANGE


def load_ground_topology_from_gml(filepath: str, default_delay: int = 1) -> Topology:

    # Naming what networkx's stub leaves untyped on `read_gml`: a graph whose nodes are the GML labels.
    graph = cast("nx.Graph[str]", nx.read_gml(filepath))  # pyright: ignore[reportUnknownMemberType]

    new_labels: dict[str, GroundStation] = {}
    ground_stations: dict[GroundStation, GroundStation] = {}
    nodes_to_remove: list[str] = []

    for node in graph.nodes():
        if not graph.nodes[node].get("Country"):
            nodes_to_remove.append(node)
            continue

        station = GroundStation(
            coordinates=(graph.nodes[node]["Latitude"], graph.nodes[node]["Longitude"], 0),
            max_connection_range=MAX_RANGE,
        )

        new_label = station

        new_labels[node] = new_label
        ground_stations[new_label] = station

    graph.remove_nodes_from(nodes_to_remove)

    # Relabelling every node left to its station: the nodes without one were removed above.
    stations_graph = cast("nx.Graph[Node]", nx.relabel_nodes(graph, new_labels))

    topology = Topology(existing_graph=stations_graph)

    for node_1, node_2, data in stations_graph.edges(data=True):
        if node_1 not in stations_graph.nodes() or node_2 not in stations_graph.nodes():
            stations_graph.remove_edge(node_1, node_2)

            continue

        link_speed = float(data.get("LinkSpeed", 0))
        link_speed_unit = data.get("LinkLabel", "M")

        bandwidth = link_speed if link_speed_unit == "M" else link_speed * 1000

        link = NetworkLink()

        link["topology"] = topology
        link["nodes"] = [node_1, node_2]
        link["bandwidth"] = bandwidth
        link["delay"] = default_delay
        link["type"] = "static"

        topology.attach_link(link)

    return topology
