"""Tests for a run the orchestrator carries out by itself.

A plan is approved once and then runs with no gate between its steps, so two
things have to hold that the step-by-step path never needed. The plan the
operator approves has to be the plan that runs, and the metrics have to stand
on their own, because nobody was watching the ticks go by.

These drive the real engine. Only the shortest runs do: measuring a snapshot
is arithmetic over a dictionary, and a handful of hand-written snapshots
exercise far more of the report than ten simulated steps would.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.actions import ActionType, RunFullSimulationPayload, build_payload
from app.core.config import SimulationConfig
from app.core.executor import execute_action
from app.core.actions import ProposedAction
from app.core.plan import SimulationPlan
from app.core.report import collect_run_metrics, measure_snapshot, share, summarize_run
from app.core.session import create_session
from app.agents.dashboard.tools import ProposalBuffer


def make_config(**changes):
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=10,
        num_satellites=8,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    return config.copy_with(**changes) if changes else config


def make_snapshot(step, users, connected, applications, allocated, links=0):
    """Builds a snapshot holding exactly the counts a measurement reads."""
    return {
        "step": step,
        "satellites": [{"id": 1, "active": True}],
        "ground_stations": [{"id": 1}, {"id": 2}],
        "links": [{"delay": 10.0} for _ in range(links)],
        "users": [
            {
                "id": index,
                "connected_aps": [{"id": 1, "class": "Satellite"}] if index < connected else [],
                "applications": [
                    {"id": index, "allocated_to": 7 if index < allocated else None}
                    for _ in range(1 if index < applications else 0)
                ],
            }
            for index in range(users)
        ],
    }


# -- The plan ---------------------------------------------------------------


def test_a_plan_without_a_step_budget_is_refused():
    try:
        SimulationPlan(make_config(), 0)
    except ValueError as error:
        assert "steps must be >= 1" in str(error)
    else:
        raise AssertionError("a plan of zero steps was accepted")


def test_the_gate_is_shown_the_whole_plan_and_not_just_the_sentence():
    """What the operator approves is a run that will not stop to ask again, so
    every setting that shapes it has to be on screen before they agree."""
    description = SimulationPlan(make_config(num_users=40, scenario="leo"), 25).describe()

    for expected in ("25 steps", "leo", "best_fit_allocation", "users=40"):
        assert expected in description, f"{expected!r} missing from {description!r}"


# -- Measuring a run --------------------------------------------------------


def test_a_scenario_with_nothing_to_place_does_not_report_a_perfect_run():
    """Zero out of zero is not success. It read as 100% provisioned, which is
    the most flattering possible answer to an empty simulation."""
    assert share(0, 0) == 0.0


def test_a_measurement_counts_what_was_placed_and_who_was_connected():
    measured = measure_snapshot(make_snapshot(3, users=4, connected=3, applications=4, allocated=1, links=2))

    assert measured["step"] == 3
    assert measured["users_total"] == 4
    assert measured["users_connected"] == 3
    assert measured["applications_total"] == 4
    assert measured["applications_allocated"] == 1
    assert measured["links"] == 2
    assert measured["mean_delay"] == 10.0


def test_a_run_is_measured_in_ticks_rather_than_in_snapshots():
    """An infrastructure change records a snapshot without moving the clock.
    Counting snapshots would report more steps than the simulation ran."""
    history = [
        make_snapshot(0, users=2, connected=2, applications=2, allocated=2),
        make_snapshot(0, users=2, connected=2, applications=2, allocated=2),
        make_snapshot(1, users=2, connected=2, applications=2, allocated=2),
    ]

    assert collect_run_metrics(history)["steps_run"] == 1


def test_the_worst_tick_is_reported_with_the_step_it_happened_on():
    """An average hides the collapse that a run is usually judged by."""
    history = [
        make_snapshot(0, users=4, connected=4, applications=4, allocated=4),
        make_snapshot(1, users=4, connected=4, applications=4, allocated=1),
        make_snapshot(2, users=4, connected=4, applications=4, allocated=3),
    ]

    metrics = collect_run_metrics(history)

    assert metrics["provisioning_worst"] == 25.0
    assert metrics["provisioning_worst_step"] == 1
    assert metrics["provisioning_final"] == 75.0


def test_a_run_that_produced_nothing_says_so_instead_of_dividing_by_zero():
    metrics = collect_run_metrics([])

    assert metrics["series"] == []
    assert "nothing to report" in summarize_run(SimulationPlan(make_config(), 5), metrics)


def test_a_report_that_fell_short_of_its_budget_says_it_was_stopped():
    history = [make_snapshot(step, users=2, connected=2, applications=2, allocated=2) for step in range(3)]

    report = summarize_run(SimulationPlan(make_config(), 50), collect_run_metrics(history))

    assert "2 of 50 steps" in report
    assert "stopped" in report.lower()


def test_a_report_that_spent_its_budget_does_not_claim_it_was_stopped():
    history = [make_snapshot(step, users=2, connected=2, applications=2, allocated=1) for step in range(6)]

    report = summarize_run(SimulationPlan(make_config(), 5), collect_run_metrics(history))

    assert "5 of 5 steps" in report
    assert "stopped" not in report.lower()


# -- Running one ------------------------------------------------------------


def test_confirming_a_plan_builds_a_new_simulation_with_the_whole_run_scheduled():
    session = create_session(make_config())
    plan = SimulationPlan(make_config(num_users=4), 3)

    result = execute_action(session, ProposedAction(ActionType.RUN_FULL_SIMULATION, RunFullSimulationPayload(plan)))

    assert result.replaces_session()
    assert result.new_session is not session
    assert result.new_session.config.num_users == 4
    assert result.new_session.steps_remaining == 3


def test_the_plan_is_handed_back_once_the_last_step_has_run():
    session = create_session(make_config(num_users=4, num_satellites=4))
    plan = SimulationPlan(session.config, 2)
    session.start_plan(plan)

    assert session.take_finished_plan() is None, "the plan was handed back mid-run"
    while session.has_pending_steps():
        session.run_next_pending_step()

    assert session.take_finished_plan() is plan
    assert session.take_finished_plan() is None, "the same run was reported twice"


def test_a_run_the_operator_stopped_is_still_reported():
    """Stopping is not cancelling: ticks ran, and there are metrics for them."""
    session = create_session(make_config(num_users=4, num_satellites=4))
    plan = SimulationPlan(session.config, 50)
    session.start_plan(plan)
    session.run_next_pending_step()
    session.stop_stepping()

    assert session.take_finished_plan() is plan
    assert collect_run_metrics(session.history)["steps_run"] == 1


def test_a_session_nobody_planned_has_no_plan_to_report():
    session = create_session(make_config())
    session.request_steps(1)
    session.run_next_pending_step()

    assert session.take_finished_plan() is None


# -- Reaching it through the agent ------------------------------------------


def test_the_tool_keeps_every_setting_the_operator_did_not_name():
    buffer = ProposalBuffer(current_config=make_config())

    buffer.propose_run_full_simulation(steps=12, num_users=40)
    plan = buffer.get_last_proposal().payload.plan

    assert plan.steps == 12
    assert plan.config.num_users == 40
    assert plan.config.scenario == "hybrid"
    assert plan.config.num_satellites == 8


def test_the_tool_refuses_a_run_before_a_simulation_has_been_loaded():
    """There is no configuration to resolve the missing settings against, and
    inventing one would run something nobody chose."""
    reply = ProposalBuffer().propose_run_full_simulation(steps=5)

    assert reply.lower().startswith("error")
    assert ProposalBuffer().get_proposals() == []


def test_a_skill_that_leaves_out_the_step_budget_is_told_which_field_is_missing():
    """Omitting a parameter is the failure this project keeps meeting, so the
    refusal has to name the field rather than raise a bare KeyError."""
    try:
        build_payload(ActionType.RUN_FULL_SIMULATION, {"num_users": 40}, current_config=make_config())
    except ValueError as error:
        assert "step budget" in str(error)
    else:
        raise AssertionError("a run was built with no step budget")


def test_a_skill_proposal_resolves_against_the_configuration_the_runner_holds():
    payload = build_payload(
        ActionType.RUN_FULL_SIMULATION, {"steps": 7, "scenario": "leo"}, current_config=make_config()
    )

    assert payload.plan.steps == 7
    assert payload.plan.config.scenario == "leo"
    assert payload.plan.config.num_users == 10


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
