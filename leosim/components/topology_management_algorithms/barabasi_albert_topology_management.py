from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING, Any

from geopy.distance import geodesic

from ..network_link import NetworkLink
from ..satellite import Satellite

if TYPE_CHECKING:
    from ...geometry import Coordinates
    from ..topology import Topology

# Weighing distance against degree: every kilometre to a target scales its attraction by exp(-DISTANCE_DECAY).
DISTANCE_DECAY = 0.05


def attraction_weights(
    topology: Topology, origin: Coordinates, targets: dict[Satellite, Coordinates]
) -> dict[Satellite, float]:
    """Weighs how strongly each target attracts a new link from a satellite at `origin`.

    The attraction is the target's degree times exp(-DISTANCE_DECAY * distance), taken
    relative to the strongest target. It is computed in log space: between satellites
    thousands of kilometres apart, exp(-0.05 * km) underflows to zero for every target,
    and zero weights cannot be normalized.

    Args:
        topology (Topology): The graph whose degrees attract the links.
        origin (tuple): Where the satellite looking for links is.
        targets (dict): The candidate satellites and their positions.

    Returns:
        dict: The targets that attract at all, each with a weight above zero and at most 1.
    """
    log_attraction = {
        target: math.log(len(topology[target])) - DISTANCE_DECAY * geodesic(origin[:2], position[:2]).kilometers
        for target, position in targets.items()
        if len(topology[target]) > 0
    }
    if not log_attraction:
        return {}

    strongest = max(log_attraction.values())
    weights = {target: math.exp(value - strongest) for target, value in log_attraction.items()}
    return {target: weight for target, weight in weights.items() if weight > 0}


def draw_without_replacement(weights: dict[Satellite, float], count: int) -> list[Satellite]:
    """Returns: list: Up to `count` distinct satellites, each drawn with probability proportional to its weight."""
    remaining = dict(weights)
    drawn = []

    while remaining and len(drawn) < count:
        (target,) = random.choices(list(remaining), weights=list(remaining.values()))
        drawn.append(target)
        del remaining[target]

    return drawn


def barabasi_albert_network(topology: Topology, min_num_links: int = 2) -> None:
    """Links each satellite to others by preferential attachment until it has `min_num_links` neighbors.

    A target is drawn with probability proportional to its degree, decaying with its
    distance. A satellite that no candidate attracts, because every candidate is still
    unlinked, gets no new link this tick.

    Args:
        topology (Topology): The graph to add the links to.
        min_num_links (int): The degree each satellite is brought up to, when enough targets attract it.
    """
    positions = {satellite: satellite.coordinates for satellite in Satellite.all() if satellite.coordinates}

    for satellite, origin in positions.items():
        targets = {
            target: position
            for target, position in positions.items()
            if target != satellite and target not in topology[satellite]
        }
        missing_links = max(min_num_links - len(topology[satellite]), 0)

        for target in draw_without_replacement(attraction_weights(topology, origin, targets), missing_links):
            link = NetworkLink()
            link["nodes"] = [satellite, target]
            link["bandwidth"] = NetworkLink.default_bandwidth
            link["delay"] = link.get_delay()
            link["type"] = "dynamic"

            topology.attach_link(link)


def barabasi_albert_topology_management(topology: Topology, **parameters: Any) -> None:
    barabasi_albert_network(topology=topology, min_num_links=parameters.get("min_num_links", 2))
