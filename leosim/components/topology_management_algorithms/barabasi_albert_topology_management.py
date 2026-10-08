from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from geopy.distance import geodesic

from ..network_link import NetworkLink
from ..satellite import Satellite

if TYPE_CHECKING:
    from ..topology import Topology


def barabasi_albert_network(topology: Topology, min_num_links: int = 2) -> None:
    satellites = [sat for sat in Satellite.all() if sat.coordinates]
    alpha = 0.05

    for satellite in satellites:
        potential_targets = [
            neighbor for neighbor in satellites if neighbor != satellite and neighbor not in topology[satellite]
        ]
        if not potential_targets:
            continue

        degrees = {node: len(list(topology[node])) for node in potential_targets}
        probabilities = []

        for target in potential_targets:
            degree = degrees[target]
            dist = geodesic(satellite.coordinates, target.coordinates).kilometers

            probability = degree * np.exp(-alpha * dist)
            probabilities.append(probability)

        probabilities = np.array(probabilities) / sum(probabilities)

        num_links = max(min_num_links - len(topology[satellite]), 0)

        selected_targets = np.random.choice(potential_targets, size=num_links, replace=False, p=probabilities)

        for target in selected_targets:
            link = NetworkLink(satellite, target)

            link["nodes"] = [satellite, target]
            link["bandwidth"] = NetworkLink.default_bandwidth
            link["delay"] = NetworkLink.get_delay()
            link["type"] = "dynamic"

            topology.attach_link(link)


def barabasi_albert_topology_management(topology: Topology, **parameters: Any) -> None:
    barabasi_albert_network(topology=topology, min_num_links=parameters.get("min_num_links", 2))
