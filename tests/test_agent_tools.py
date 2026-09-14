"""Tests for the agent tools and the typed actions.

No Streamlit mock is needed: the tools record proposals in their own buffer,
without touching any global interface state.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.tools import ProposalBuffer
from app.core.actions import ActionType
from app.core.config import SimulationConfig


def make_config():
    return SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=20,
        num_satellites=15,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )


def test_run_simulation_registers_typed_proposal():
    buffer = ProposalBuffer()
    message = buffer.propose_run_simulation(5)

    assert "Proposal registered" in message
    assert len(buffer.get_proposals()) == 1

    action = buffer.get_last_proposal()
    assert action.action_type == ActionType.RUN_SIMULATION
    assert action.payload.steps == 5


def test_invalid_input_returns_message_instead_of_raising():
    buffer = ProposalBuffer()

    assert buffer.propose_run_simulation(0).startswith("Error:")
    assert buffer.propose_add_user(999.0, 0.0, 1500).startswith("Error:")
    assert buffer.propose_add_process_unit("Router", 1, 10, 10).startswith("Error:")
    assert buffer.get_proposals() == []


def test_add_node_accepts_json_strings_from_the_model():
    buffer = ProposalBuffer()
    buffer.propose_add_node('["Satellite"]', "[-21.0]", "[-47.8]", "[550.0]")

    action = buffer.get_last_proposal()
    assert action.action_type == ActionType.ADD_NODES
    assert len(action.payload.nodes) == 1
    assert action.payload.nodes[0].node_type == "Satellite"


def test_add_node_rejects_mismatched_parallel_lists():
    buffer = ProposalBuffer()
    message = buffer.propose_add_node(["Satellite", "Satellite"], [-21.0], [-47.8], [550.0])

    assert message.startswith("Error:")
    assert buffer.get_proposals() == []


def test_repeated_add_node_calls_merge_into_one_proposal():
    buffer = ProposalBuffer()
    buffer.propose_add_node(["Satellite"], [-21.0], [-47.8], [550.0])
    buffer.propose_add_node(["Satellite"], [-21.01], [-47.8], [550.0])

    assert len(buffer.get_proposals()) == 1
    assert len(buffer.get_last_proposal().payload.nodes) == 2


def test_restart_keeps_current_values_for_omitted_arguments():
    buffer = ProposalBuffer(current_config=make_config())
    buffer.propose_restart_simulation(num_users=50)

    config = buffer.get_last_proposal().payload.config
    assert config.num_users == 50
    assert config.scenario == "hybrid"
    assert config.gml_path == "datasets/rnp.gml"


def test_restart_without_loaded_simulation_is_refused():
    buffer = ProposalBuffer(current_config=None)
    assert buffer.propose_restart_simulation().startswith("Error:")


def test_adding_a_unit_and_adding_nodes_are_distinct_actions():
    """Each proposal must carry its own action type. Sharing one type across
    incompatible payload shapes is what let a malformed proposal reach the
    executor."""
    unit_buffer = ProposalBuffer()
    unit_buffer.propose_add_process_unit("GroundStation", 28, 50, 50)

    nodes_buffer = ProposalBuffer()
    nodes_buffer.propose_add_node(["Satellite"], [-21.0], [-47.8], [550.0])

    unit_action = unit_buffer.get_last_proposal()
    nodes_action = nodes_buffer.get_last_proposal()

    assert unit_action.action_type == ActionType.ADD_PROCESS_UNIT
    assert nodes_action.action_type == ActionType.ADD_NODES
    assert unit_action.action_type != nodes_action.action_type

    assert unit_action.payload.target_type == "GroundStation"
    assert unit_action.payload.target_id == 28
    assert nodes_action.payload.nodes[0].lat == -21.0


def test_tool_list_exposes_every_proposal_tool():
    buffer = ProposalBuffer()
    names = [tool.__name__ for tool in buffer.get_tools()]

    assert sorted(names) == sorted([
        "propose_run_simulation",
        "propose_restart_simulation",
        "propose_add_process_unit",
        "propose_add_user",
        "propose_add_app_to_user",
        "propose_add_node",
    ])


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
