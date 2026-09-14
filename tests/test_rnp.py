"""Smoke test for loading the RNP scenario.

Checks that the shipped datasets produce a coherent simulation: the loaded
scenario matches the requested configuration, and the first snapshot carries
every section the map and the agent read.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import SimulationConfig
from app.core.session import create_session
from leosim.components import GroundStation, Satellite, User

GML = "datasets/rnp.gml"
TRACES = "datasets/satellites_brazil.json"
NUM_USERS = 20
NUM_SATELLITES = 15


def make_session():
    config = SimulationConfig(
        gml_path=GML,
        satellites_path=TRACES,
        num_users=NUM_USERS,
        num_satellites=NUM_SATELLITES,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    return create_session(config)


def test_the_scenario_matches_the_requested_configuration():
    make_session()

    assert User.count() == NUM_USERS
    assert Satellite.count() == NUM_SATELLITES
    assert GroundStation.count() > 0


def test_the_first_snapshot_carries_every_section():
    snapshot = make_session().get_current_snapshot()

    for section in ("step", "label", "satellites", "ground_stations", "users", "links"):
        assert section in snapshot, f"snapshot is missing '{section}'"

    assert snapshot["step"] == 0
    assert len(snapshot["users"]) == NUM_USERS
    assert len(snapshot["satellites"]) > 0
    assert len(snapshot["links"]) > 0


def test_the_hybrid_scenario_places_process_units_on_both_sides():
    make_session()

    satellites_with_units = [s for s in Satellite.all() if s.process_unit]
    stations_with_units = [g for g in GroundStation.all() if g.process_unit]

    assert satellites_with_units, "no satellite received a process unit"
    assert stations_with_units, "no ground station received a process unit"


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
