"""Tests for the execution of confirmed actions.

None of these tests advances the simulation clock, by design: a tick costs
several seconds of topology management and these tests do not need one.
"""

from collections.abc import Callable

from app.agents.dashboard.tools import ProposalBuffer
from app.core.action_result import ActionResult
from app.core.config import SimulationConfig
from app.core.executor import execute_action
from app.core.session import SimulationSession, create_session
from leosim.components import GroundStation, Satellite, User
from tests.proposals import last_proposal


def make_session() -> SimulationSession:
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=5,
        num_satellites=4,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    return create_session(config)


def apply(session: SimulationSession, build_proposal: Callable[[ProposalBuffer], object]) -> ActionResult:
    buffer = ProposalBuffer(current_config=session.config)
    build_proposal(buffer)
    return execute_action(session, last_proposal(buffer))


def test_added_satellite_continues_the_internal_numbering() -> None:
    """A satellite created by the operator must take the next internal id in
    sequence, like the ones loaded from the scenario."""
    session = make_session()
    ids_before = {satellite.id for satellite in Satellite.all()}
    expected_id = max(ids_before) + 1

    apply(session, lambda buffer: buffer.propose_add_node(["Satellite"], [-7.23], [-35.88], [550.0]))

    new_satellites = [satellite for satellite in Satellite.all() if satellite.id not in ids_before]
    assert len(new_satellites) == 1
    assert new_satellites[0].id == expected_id
    assert new_satellites[0].name == f"Satellite_{expected_id}"


def test_infrastructure_changes_never_advance_the_clock() -> None:
    session = make_session()

    apply(session, lambda buffer: buffer.propose_add_node(["Satellite"], [-7.23], [-35.88], [550.0]))
    apply(session, lambda buffer: buffer.propose_add_user(-23.5, -46.6, 1500))
    apply(session, lambda buffer: buffer.propose_add_process_unit("GroundStation", 1, 50, 50))

    assert session.simulator.scheduler.steps == 0


def test_every_infrastructure_change_publishes_its_own_snapshot() -> None:
    session = make_session()
    snapshots_before = session.get_step_count()

    apply(session, lambda buffer: buffer.propose_add_user(-23.5, -46.6, 1500))

    assert session.get_step_count() == snapshots_before + 1
    assert session.is_viewing_latest()


def test_timeline_labels_separate_ticks_from_changes() -> None:
    """The timeline must name each snapshot after the tick it belongs to, so
    changes made within step 0 never read as step 1."""
    session = make_session()
    apply(session, lambda buffer: buffer.propose_add_user(-23.5, -46.6, 1500))
    apply(session, lambda buffer: buffer.propose_add_user(-22.9, -43.2, 1500))

    assert session.get_snapshot_labels() == ["Step 0", "Step 0 · change 1", "Step 0 · change 2"]


def test_attaching_a_server_to_a_station_without_one_works() -> None:
    """A station that was serialized without servers must still accept its
    first one."""
    session = make_session()
    station = GroundStation.all()[0]
    station.process_unit = None

    apply(session, lambda buffer: buffer.propose_add_process_unit("GroundStation", station.id, 50, 50))

    assert station.process_unit is not None
    assert len(station.process_unit) == 1


def test_adding_an_application_to_an_unknown_user_is_reported() -> None:
    session = make_session()
    result = apply(session, lambda buffer: buffer.propose_add_app_to_user(9999, 10, 10))

    assert result.toast is not None
    assert "not found" in result.toast


def test_an_application_added_mid_run_is_requested_on_the_next_step() -> None:
    """Measured 11 October 2026: an application added at step 5 had its first access
    scheduled from step 1, already under way, so its user only requested it at the
    next access, on step 29, and it stayed unallocated all the while."""
    session = make_session()
    # Setting the clock by hand: the access is scheduled against it, and no tick is needed.
    session.simulator.scheduler.steps = 5
    user = User.find_by("id", 1)
    assert user is not None

    apply(session, lambda buffer: buffer.propose_add_app_to_user(1, 25, 30))
    access_model = user.applications_access_models[-1]
    user.follow_access(access_model)

    assert access_model.history[-1]["start"] == 6
    assert access_model.request_provisioning, "the application is not requested on the step after it was added"
