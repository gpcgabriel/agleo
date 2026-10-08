"""Tests for the routes the topology finds between users and process units.

Every network here is built by hand: a few nodes and the links between them,
so each route can be read off the drawing in the test.
"""

from itertools import pairwise

from leosim import Simulator, clear_components
from leosim.components import (
    Application,
    FixedDurationAccessModel,
    GroundStation,
    NetworkFlow,
    NetworkLink,
    ProcessUnit,
    Satellite,
    Topology,
    User,
)
from leosim.components.topology import Node


def connect(topology: Topology, node: Node, other: Node, delay: float = 1.0) -> NetworkLink:
    link = NetworkLink()
    link["nodes"] = [node, other]
    link["delay"] = delay
    topology.attach_link(link)
    return link


def make_network() -> tuple[Topology, GroundStation, Satellite, ProcessUnit, User]:
    """Returns: tuple: station - satellite - unit in a row, and a user served by the station."""
    clear_components()
    topology = Simulator().topology
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    satellite = Satellite(coordinates=(0.0, 1.0, 550.0))
    unit = ProcessUnit()
    connect(topology, station, satellite)
    connect(topology, satellite, unit)
    user = User(coordinates=(0.0, 0.0, 0.0))
    user.network_access_points = [station]
    return topology, station, satellite, unit, user


def test_a_route_starts_at_the_users_access_point() -> None:
    topology, station, satellite, unit, user = make_network()

    assert topology.path_from_access_points(user, unit) == [station, satellite, unit]


def test_an_unreachable_unit_gives_an_empty_route() -> None:
    topology, _station, _satellite, _unit, user = make_network()
    isolated = ProcessUnit()
    topology.add_node(isolated)

    assert topology.path_from_access_points(user, isolated) == []


def test_the_access_point_with_fewer_hops_gives_the_route() -> None:
    topology, station, satellite, unit, user = make_network()
    user.network_access_points = [station, satellite]

    assert topology.path_from_access_points(user, unit) == [satellite, unit]


def test_a_flow_with_no_request_mark_is_rerouted_from_its_users_access_point() -> None:
    topology, station, satellite, unit, user = make_network()
    flow = NetworkFlow(source=user, target=unit)

    topology.reroute_flows()

    assert flow.path == [station, satellite, unit]
    assert flow.status == "active"
    assert all(flow in topology.link_between(node, other)["flows"] for node, other in pairwise(flow.path))


def test_the_exported_topology_lists_the_satellites_users_reach() -> None:
    topology, _station, satellite, _unit, user = make_network()
    user.network_access_points = [satellite]

    exported = topology.export_topology()

    assert [(link["user"], link["sat"]) for link in exported["user_sat"]] == [(user.id, satellite.id)]


def test_a_users_delay_counts_the_wireless_hop_once() -> None:
    topology, station, satellite, unit, user = make_network()
    station.wireless_delay = 5
    access_model = FixedDurationAccessModel(
        user=user,
        application=Application(),
        duration_values=[5],
        interval_values=[1],
        connection_duration_values=[5],
        connection_interval_values=[1],
    )
    user.applications_access_models = [access_model]
    access_model.flow = NetworkFlow(source=user, target=unit, path=[station, satellite, unit])

    delays = [access["Delay"] for access in user.collect_metrics()["Access to Applications"]]

    assert topology.get_path_delay([station, satellite, unit]) == 7
    assert delays == [7]
