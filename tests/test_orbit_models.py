"""Tests for the models that move a satellite along its orbit.

Each drives one satellite through `Satellite.step` with the simulator's clock
set by hand, so no topology or user has to exist.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leosim import Simulator, clear_components
from leosim.components import Satellite, coordinates_history
from leosim.geometry import Coordinates

FIRST = (-10.0, -47.0, 550.0)
SECOND = (-11.0, -47.5, 550.0)
THIRD = (-12.0, -48.0, 550.0)


def positions_over(satellite: Satellite, steps: int) -> list[Coordinates | None]:
    """Returns: list: Where the satellite stands at each of the first `steps` ticks."""
    simulator = Simulator()
    positions = []
    for step in range(steps):
        simulator.scheduler.steps = step
        satellite.step()
        positions.append(satellite.coordinates)
    return positions


def test_coordinates_history_replays_the_recorded_trace_in_a_loop() -> None:
    clear_components()
    satellite = Satellite(coordinates=FIRST, mobility_model=coordinates_history)
    satellite.coordinates_trace = [FIRST, SECOND, THIRD]

    assert positions_over(satellite, 7) == [FIRST, SECOND, THIRD, FIRST, SECOND, THIRD, FIRST]
    assert satellite.mobility_model_parameters["len"] == 3


def test_coordinates_history_follows_a_period_the_scenario_sets() -> None:
    clear_components()
    satellite = Satellite(coordinates=FIRST, mobility_model=coordinates_history)
    satellite.coordinates_trace = [FIRST, SECOND, THIRD]
    satellite.mobility_model_parameters = {"len": 2}

    assert positions_over(satellite, 5) == [FIRST, SECOND, THIRD, SECOND, FIRST]


def test_coordinates_history_refuses_a_satellite_with_nothing_recorded() -> None:
    clear_components()
    satellite = Satellite(mobility_model=coordinates_history)

    try:
        positions_over(satellite, 1)
    except ValueError as error:
        assert str(satellite) in str(error)
    else:
        raise AssertionError("an empty recording was replayed")


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
