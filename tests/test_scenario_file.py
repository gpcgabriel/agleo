"""Tests for the component registry and the scenario file round trip.

`ComponentManager.save_scenary` writes a scenario file and `Simulator.initialize`
reads it back. These check what the round trip keeps: once loaded, every link
belongs to the simulator's topology, so the scenario can be saved again.
"""

import json
import os
import sys
import tempfile

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.bootstrap import build_simulator
from app.core.config import SimulationConfig
from leosim import ComponentManager, Simulator, clear_components
from leosim.components import NetworkLink, Topology


def make_simulator(directory: str) -> Simulator:
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=6,
        num_satellites=4,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    return build_simulator(config, scenary_path=os.path.join(directory, "scenario.json"), logs_directory=directory)


def test_every_loaded_link_belongs_to_the_simulators_topology() -> None:
    with tempfile.TemporaryDirectory() as directory:
        simulator = make_simulator(directory)

    assert NetworkLink.count() > 0
    assert all(link["topology"] is simulator.topology for link in NetworkLink.all())


def test_a_loaded_scenario_can_be_saved_again() -> None:
    with tempfile.TemporaryDirectory() as directory:
        simulator = make_simulator(directory)
        resaved = os.path.join(directory, "resaved.json")
        ComponentManager.save_scenary(filename=resaved)

        with open(resaved, encoding="utf-8") as file:
            links = json.load(file)["NetworkLink"]

    assert links
    assert {link["relationships"]["topology"]["id"] for link in links} == {simulator.topology.id}


def test_clearing_a_link_empties_that_link_and_keeps_the_registry() -> None:
    clear_components()
    kept = NetworkLink()
    cleared = NetworkLink()

    cleared.clear()

    assert NetworkLink.count() == 2
    assert dict(cleared) == {}
    assert kept["id"] == 1


def test_a_topology_built_from_a_graph_keeps_the_registry_and_the_edges() -> None:
    clear_components()
    first = Topology()
    graph = nx.Graph()
    graph.add_edge("a", "b")

    second = Topology(existing_graph=graph)

    assert Topology.all() == [first, second]
    assert list(second.edges()) == [("a", "b")]


def test_topologies_get_their_own_ids() -> None:
    clear_components()

    assert [Topology().id, Topology().id] == [1, 2]


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
