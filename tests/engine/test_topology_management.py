"""Tests for the algorithms that add links between satellites on every tick."""

import os
import random
import tempfile
from collections.abc import Sequence

from app.core.bootstrap import build_scenario
from app.core.config import SimulationConfig
from leosim import Simulator, clear_components
from leosim.components import (
    NetworkLink,
    Satellite,
    Topology,
    barabasi_albert_topology_management,
    best_fit_allocation,
)
from leosim.components.topology_management_algorithms.barabasi_albert_topology_management import (
    barabasi_albert_network,
)
from leosim.geometry import Coordinates

ROW_OF_FIVE = [(-10.0 - index * 0.5, -47.0, 550.0) for index in range(5)]


def link(topology: Topology, node: Satellite, other: Satellite) -> None:
    connection = NetworkLink()
    connection["nodes"] = [node, other]
    topology.attach_link(connection)


def make_satellites(positions: Sequence[Coordinates]) -> tuple[Topology, list[Satellite]]:
    """Returns: tuple: A topology holding one satellite per position, none of them linked yet."""
    clear_components()
    topology = Topology()
    satellites = [Satellite(coordinates=position) for position in positions]
    for satellite in satellites:
        topology.add_node(satellite)
    return topology, satellites


def make_chain(positions: Sequence[Coordinates]) -> tuple[Topology, list[Satellite]]:
    """Returns: tuple: Satellites at the given positions, each linked to the next so every one has a degree."""
    topology, satellites = make_satellites(positions)
    for satellite, following in zip(satellites, satellites[1:], strict=False):
        link(topology, satellite, following)
    return topology, satellites


def test_barabasi_albert_brings_every_satellite_up_to_the_minimum_degree() -> None:
    topology, satellites = make_chain(ROW_OF_FIVE)
    random.seed(1)

    barabasi_albert_network(topology, min_num_links=3)

    assert all(len(topology[satellite]) >= 3 for satellite in satellites)
    added = [connection for connection in NetworkLink.all() if connection["type"] == "dynamic"]
    assert added
    assert all(connection["topology"] is topology and connection["delay"] > 0 for connection in added)


def test_barabasi_albert_draws_the_same_links_under_the_same_seed() -> None:
    drawn = []
    for _ in range(2):
        topology, _satellites = make_chain(ROW_OF_FIVE)
        random.seed(7)
        barabasi_albert_network(topology, min_num_links=3)
        drawn.append(sorted(tuple(sorted((str(node), str(other)))) for node, other in topology.edges()))

    assert drawn[0] == drawn[1]


def test_barabasi_albert_prefers_the_nearer_targets_even_where_the_attraction_underflows() -> None:
    """Both clusters lie over 15 000 km away, where exp(-0.05 * km) is zero in floating point."""
    topology, (origin, near, near_partner, far, far_partner) = make_satellites(
        [(0.0, 0.0, 550.0), (0.0, 140.0, 550.0), (0.0, 140.3, 550.0), (0.0, 179.0, 550.0), (0.0, 179.3, 550.0)]
    )
    link(topology, near, near_partner)
    link(topology, far, far_partner)
    random.seed(3)

    barabasi_albert_network(topology, min_num_links=1)

    assert set(topology[origin]) <= {near, near_partner}
    assert len(topology[origin]) == 1


def test_barabasi_albert_runs_as_the_simulators_topology_management() -> None:
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=4,
        num_satellites=6,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    with tempfile.TemporaryDirectory() as directory:
        scenario = build_scenario(config, scenary_path=os.path.join(directory, "scenario.json"))
        simulator = Simulator(
            resource_management_algorithm=best_fit_allocation,
            topology_management_algorithm=barabasi_albert_topology_management,
            topology_management_algorithm_parameters={"min_num_links": 3},
            logs_directory=directory,
        )
        simulator.initialize(scenario)
        for _ in range(3):
            simulator.step()

    satellite_links = [
        connection
        for connection in NetworkLink.all()
        if all(isinstance(node, Satellite) for node in connection["nodes"])
        and simulator.topology.has_edge(*connection["nodes"])
    ]
    assert satellite_links
    assert all(connection["type"] == "dynamic" for connection in satellite_links)
