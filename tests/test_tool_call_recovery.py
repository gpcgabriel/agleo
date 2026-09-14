"""Tests for recovering tool calls emitted as plain text."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.tool_call_recovery import looks_like_tool_call, parse_tool_call, recover
from app.agents.tools import ProposalBuffer
from app.core.actions import ActionType

# The exact text a model returned instead of calling the tool.
OBSERVED_BLOB = (
    '{"name": "propose_add_node", "parameters": {"node_types": ["Satellite"], '
    '"latitudes": [-7.2306 - 0.01], "longitudes": [-35.8811], "altitudes": [500]}}'
)


def test_recovers_the_call_observed_in_the_dashboard():
    buffer = ProposalBuffer()
    assert recover(buffer, OBSERVED_BLOB) is not None

    action = buffer.get_last_proposal()
    assert action.action_type == ActionType.ADD_NODES
    assert abs(action.payload.nodes[0].lat - (-7.2406)) < 1e-6, "the arithmetic was not evaluated"


def test_plain_prose_is_not_mistaken_for_a_tool_call():
    assert parse_tool_call("There are 8 active satellites in the constellation.") is None
    assert not looks_like_tool_call("Ground Station 3 has no servers attached.")


def test_alternative_field_names_are_accepted():
    buffer = ProposalBuffer()
    assert recover(buffer, '{"tool": "propose_run_simulation", "arguments": {"steps": 4}}') is not None
    assert buffer.get_last_proposal().payload.steps == 4


def test_a_call_embedded_in_surrounding_prose_is_found():
    buffer = ProposalBuffer()
    text = 'Sure, I will do that:\n{"name": "propose_run_simulation", "parameters": {"steps": 2}}\nConfirm below.'
    assert recover(buffer, text) is not None
    assert buffer.get_last_proposal().payload.steps == 2


def test_code_in_the_payload_is_refused():
    """The evaluator accepts data and arithmetic; any call is refused."""
    hostile = '{"name": "propose_run_simulation", "parameters": {"steps": __import__("os").system("id")}}'
    assert parse_tool_call(hostile) is None


def test_unknown_tool_names_are_ignored():
    buffer = ProposalBuffer()
    assert recover(buffer, '{"name": "delete_everything", "parameters": {}}') is None
    assert buffer.get_proposals() == []


def test_wrong_arguments_do_not_raise():
    buffer = ProposalBuffer()
    result = recover(buffer, '{"name": "propose_run_simulation", "parameters": {"ticks": 3}}')
    assert result.startswith("Error:")
    assert buffer.get_proposals() == []


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
