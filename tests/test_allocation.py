"""Tests for the LLM-driven allocation strategy.

Most of these exercise state selection, prompt building and decision handling,
which need no model at all. Only the last one talks to Ollama, and it acts on
a single ground station: a full tick asks every station in turn, which costs
minutes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.allocation.allocator import LLMAllocator
from app.agents.allocation.decision import AllocationDecision, split_without_duplicates
from app.agents.allocation.prompt import build_allocation_prompt, build_history_section
from app.agents.allocation.state import collect_state, find_pending_app_ids, should_skip
from app.core.config import SimulationConfig
from app.core.session import create_session
from app.helper_functions.ollama_helper import is_ollama_running, list_local_models
from leosim.components import GroundStation


def make_session():
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=8,
        num_satellites=6,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    return create_session(config)


def resolve_model():
    """Returns: str or None: A local model usable for the integration test."""
    if not is_ollama_running():
        return None

    models = list_local_models()
    return models[0] if models else None


# -- Decision handling ------------------------------------------------------


def test_an_application_is_never_placed_by_two_strategies():
    decision = AllocationDecision(best_fit=[1, 2], longest_duration=[2, 3])
    best_fit, longest_duration = split_without_duplicates(decision)

    assert best_fit == [1, 2]
    assert longest_duration == [3]
    assert not set(best_fit) & set(longest_duration)


def test_an_empty_decision_is_valid():
    best_fit, longest_duration = split_without_duplicates(AllocationDecision())

    assert best_fit == []
    assert longest_duration == []


# -- State selection --------------------------------------------------------


def test_only_pending_applications_are_collected():
    all_apps = {"App_1": {"pending": True}, "App_2": {"pending": False}, "App_3": {"pending": True}}

    assert sorted(find_pending_app_ids(all_apps)) == [1, 3]


def test_a_station_with_nothing_it_can_serve_is_skipped():
    """The list `should_skip` receives is the station's own, not the network's."""
    session = make_session()
    station = GroundStation.all()[0]

    assert should_skip(station, [], {1, 2}) == "no servable pending apps"


def test_a_station_with_no_reach_and_no_server_is_skipped():
    session = make_session()
    station = GroundStation.all()[0]
    station.process_unit = []

    assert should_skip(station, [1], set()) == "no satellites or process units in range"


def test_collect_state_reports_a_skip_reason_instead_of_a_partial_state():
    session = make_session()
    station = GroundStation.all()[0]

    state, pending, reason = collect_state(session.simulator, station, "hybrid")

    if reason:
        assert state is None and pending is None
    else:
        for section in (
            "step",
            "scenario",
            "ground_station",
            "satellites",
            "users",
            "process_units",
            "unit_hosts",
            "applications",
            "topology",
        ):
            assert section in state, f"state is missing '{section}'"


def test_every_process_unit_records_where_it_sits():
    """A unit in orbit and a unit on the ground are reached by different paths.

    `build_network_state` drops each satellite's `pu` field after collecting
    the unit ids, so the link has to be recorded before that happens or the
    digest cannot say which satellite a unit rides on.
    """
    session = make_session()

    for station in GroundStation.all():
        state, pending, reason = collect_state(session.simulator, station, "hybrid")
        if reason:
            continue

        for unit_key in state["process_units"]:
            host = state["unit_hosts"].get(unit_key)
            assert host is not None, f"{unit_key} has no recorded host"
            assert host.startswith("Sat_") or host.startswith("GS_"), f"{unit_key} sits on {host!r}"


# -- Prompt -----------------------------------------------------------------


def test_the_prompt_names_the_pending_applications():
    prompt = build_allocation_prompt({"step": 0}, [7, 9], [])

    assert "[7, 9]" in prompt


def test_the_prompt_carries_the_digest_rather_than_serialized_state():
    prompt = build_allocation_prompt({"step": 0}, [7, 9], [])

    assert "PLACE THESE APPLICATIONS" in prompt
    assert "PROCESS UNITS IN REACH" in prompt
    assert "{" not in prompt, "the state is being serialized, not rendered"


def test_history_is_absent_until_there_is_one():
    assert build_history_section([]) == ""

    entry = {"step": 1, "best_fit": [1], "longest_duration": [], "results": {"provisioned": 1, "failed": 0}}
    section = build_history_section([entry])

    assert "Step 1" in section
    assert "provisioned=1" in section


# -- Injection --------------------------------------------------------------


def test_the_allocator_is_shaped_like_a_plain_allocation_algorithm():
    """The engine injects it exactly like best_fit_allocation, which is what
    keeps the LLM stack out of `leosim`."""
    import inspect

    allocator = LLMAllocator(model_name="unused")
    parameters = list(inspect.signature(allocator.allocate).parameters)

    assert parameters == ["model", "parameters"]


def test_decisions_are_kept_per_ground_station():
    allocator = LLMAllocator(model_name="unused")

    assert allocator.get_decisions(1) == []
    allocator.get_decisions(1).append({"step": 0})

    assert len(allocator.get_decisions(1)) == 1
    assert allocator.get_decisions(2) == []


# -- Integration ------------------------------------------------------------


def test_one_station_decides_through_the_model():
    model_name = resolve_model()
    if model_name is None:
        print("  SKIP  test_one_station_decides_through_the_model (Ollama unavailable)")
        return

    session = make_session()

    # Ticking once so the access models activate and the applications become
    # pending. The session is built with a plain algorithm, so this is cheap.
    session.advance_one_step()

    allocator = LLMAllocator(model_name=model_name, logs_directory="logs/test")

    decided = False
    for station in GroundStation.all():
        _, _, reason = collect_state(session.simulator, station, "hybrid")
        if reason:
            continue

        allocator.allocate(session.simulator, {"ground_station": station, "scenario": "hybrid"})
        decided = True
        break

    if not decided:
        print("  SKIP  test_one_station_decides_through_the_model (no station had work)")
        return

    recorded = sum(len(v) for v in allocator.decisions_by_station.values())
    assert recorded == 1, f"expected one recorded decision, got {recorded}"


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
