"""Tests for how a satellite enters and leaves service as it steps.

One satellite carrying a unit, linked to a ground station, over a user it can
reach. The clock is set by hand, so each test reads as a sequence of ticks.
"""

from leosim import Simulator, clear_components
from leosim.components import GroundStation, NetworkLink, ProcessUnit, Satellite, User

POSITION = (0.0, 1.0, 550.0)


def fails_on_step_one(satellite: Satellite) -> bool:
    return satellite.model.scheduler.steps == 1


def make_satellite() -> tuple[Simulator, Satellite, User]:
    """Returns: tuple: The simulator, a satellite with a unit and a station link, and a user within its reach."""
    clear_components()
    simulator = Simulator()
    satellite = Satellite(coordinates=POSITION)
    satellite.coordinates_trace = [POSITION, POSITION, POSITION]
    satellite.process_unit = ProcessUnit()
    satellite.failure_model = fails_on_step_one
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    link = NetworkLink()
    link["nodes"] = [satellite, station]
    simulator.topology.attach_link(link)
    user = User(coordinates=(0.0, 0.0, 0.0), max_connection_range=1500)
    return simulator, satellite, user


def step(simulator: Simulator, satellite: Satellite, tick: int) -> None:
    simulator.scheduler.steps = tick
    satellite.step()


def test_a_satellite_in_service_connects_the_users_in_reach() -> None:
    simulator, satellite, user = make_satellite()

    step(simulator, satellite, 0)

    assert satellite.active
    assert user.network_access_points == [satellite]


def test_a_failing_satellite_leaves_service_its_users_and_its_links() -> None:
    simulator, satellite, user = make_satellite()
    step(simulator, satellite, 0)

    step(simulator, satellite, 1)

    assert not satellite.active
    assert satellite.process_unit is not None and not satellite.process_unit.available
    assert satellite not in user.network_access_points
    assert list(simulator.topology.neighbors(satellite)) == []


def test_a_satellite_that_stops_failing_returns_to_service() -> None:
    simulator, satellite, _user = make_satellite()
    for tick in range(3):
        step(simulator, satellite, tick)

    assert satellite.active
    assert satellite.process_unit is not None and satellite.process_unit.available
