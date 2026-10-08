"""Tests for the models that move a satellite along its orbit.

Each drives one satellite through `Satellite.step` with the simulator's clock
set by hand, so no topology or user has to exist.
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.bootstrap import build_simulator
from app.core.config import SimulationConfig
from leosim import Simulator, clear_components
from leosim.components import ProcessUnit, Satellite, coordinates_history, linear_estimation
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


def test_a_satellite_the_capture_has_not_seen_stays_out_of_service_until_its_first_position() -> None:
    clear_components()
    satellite = Satellite(mobility_model=linear_estimation)
    satellite.coordinates_trace = [None, FIRST, SECOND]
    satellite.process_unit = ProcessUnit()
    simulator = Simulator()
    service = []

    for step in range(3):
        simulator.scheduler.steps = step
        satellite.step()
        service.append((satellite.coordinates, satellite.active, satellite.process_unit.available))

    assert service == [(None, False, False), (FIRST, True, True), (SECOND, True, True)]


def test_a_satellite_first_seen_just_before_a_gap_stands_still() -> None:
    """Its only position is one step old and the slot before it is empty, so it has no velocity yet."""
    clear_components()
    satellite = Satellite(mobility_model=linear_estimation)
    satellite.coordinates_trace = [None, FIRST]

    assert positions_over(satellite, 3) == [None, FIRST, FIRST]


def sighting(satellite_id: int, latitude: float) -> dict[str, object]:
    return {
        "satid": satellite_id,
        "satname": f"STARLINK-{satellite_id}",
        "intDesignator": "2019-074A",
        "launchDate": "2019-11-11",
        "satlat": latitude,
        "satlng": -47.0,
        "satalt": 550.0,
    }


def test_a_run_whose_first_capture_misses_a_satellite_steps_on() -> None:
    """Above 343 satellites the shipped traces hold satellites first seen after step 0; such a run used to stop."""
    steps = [[sighting(1, -15.0)]] + [[sighting(1, -15.0 - step), sighting(2, -20.0 - step)] for step in range(1, 4)]

    with tempfile.TemporaryDirectory() as directory:
        traces = os.path.join(directory, "traces.json")
        with open(traces, "w", encoding="utf-8") as file:
            json.dump(steps, file)
        config = SimulationConfig("datasets/rnp.gml", traces, 2, 2, "hybrid", "best_fit_allocation")
        simulator = build_simulator(
            config, scenary_path=os.path.join(directory, "scenario.json"), logs_directory=directory
        )

        late = Satellite.find_by("id", 2)
        assert late is not None
        service = []
        for _ in range(3):
            simulator.step()
            service.append(late.active)

    assert service == [False, True, True]


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
