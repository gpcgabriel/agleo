"""Tests for the simulation session.

They drive the real engine without Streamlit: no part of these tests needs an
interface mock, which is possible because the simulation state lives in a
session object rather than in `st.session_state`.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import SimulationConfig
from app.core.session import create_session
from leosim.components import User


def make_session():
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=10,
        num_satellites=8,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    return create_session(config)


def count_connected_users(snapshot):
    return sum(1 for user in snapshot["users"] if user["connected_aps"])


def test_session_starts_at_step_zero_with_one_snapshot():
    session = make_session()

    assert session.simulator.scheduler.steps == 0
    assert session.get_step_count() == 1
    assert session.current_step_index == 0
    assert session.is_viewing_latest()


def test_initial_snapshot_already_shows_connectivity():
    """Step 0 must reflect real connectivity: users already in range have to
    show as connected before any tick runs."""
    session = make_session()
    assert count_connected_users(session.get_current_snapshot()) > 0


def test_infrastructure_change_publishes_a_snapshot_without_advancing_time():
    session = make_session()
    steps_before = session.simulator.scheduler.steps
    snapshots_before = session.get_step_count()

    session.apply_infrastructure_change()

    assert session.simulator.scheduler.steps == steps_before, "the change advanced the clock"
    assert session.get_step_count() == snapshots_before + 1, "the change produced no snapshot"
    assert session.is_viewing_latest(), "the operator is not seeing the result of the change"


def test_repeated_connectivity_refresh_does_not_duplicate_access_points():
    session = make_session()
    session.refresh_connectivity()
    session.refresh_connectivity()

    for user in User.all():
        identifiers = [id(access_point) for access_point in user.network_access_points]
        assert len(identifiers) == len(set(identifiers)), f"User {user.id} has a duplicated access point"


def test_advancing_a_step_moves_the_clock_and_the_history():
    session = make_session()
    session.advance_one_step()

    assert session.simulator.scheduler.steps == 1
    assert session.get_step_count() == 2
    assert session.get_current_snapshot()["step"] == 1


def test_scheduled_steps_are_consumed_one_at_a_time():
    session = make_session()
    session.request_steps(3)

    assert session.has_pending_steps()
    assert session.run_next_pending_step() is False
    assert session.run_next_pending_step() is False
    assert session.run_next_pending_step() is True
    assert not session.has_pending_steps()
    assert session.simulator.scheduler.steps == 3


def test_stopping_discards_the_remaining_scheduled_steps():
    session = make_session()
    session.request_steps(5)
    session.run_next_pending_step()
    session.stop_stepping()

    assert not session.has_pending_steps()
    assert session.simulator.scheduler.steps == 1


def test_viewing_an_older_step_is_reported_as_not_latest():
    session = make_session()
    session.advance_one_step()
    session.view_step(0)

    assert not session.is_viewing_latest()
    assert session.get_current_snapshot()["step"] == 0


def test_viewing_a_step_outside_the_history_is_refused():
    session = make_session()
    try:
        session.view_step(99)
    except IndexError:
        return
    raise AssertionError("expected IndexError for a step outside the history")


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
