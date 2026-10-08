"""Tests for recovering tool calls emitted as plain text."""

from app.agents.dashboard.runner import UNUSABLE_TOOL_CALL_MESSAGE, answer_for_a_reply_that_is_a_call
from app.agents.dashboard.tool_call_recovery import looks_like_tool_call, parse_tool_call, recover
from app.agents.dashboard.tools import ProposalBuffer
from app.core.actions import ActionType, AddNodesPayload, RunSimulationPayload
from tests.proposals import last_proposal

# Holding the exact text a model returned instead of calling the tool.
OBSERVED_BLOB = (
    '{"name": "propose_add_node", "parameters": {"node_types": ["Satellite"], '
    '"latitudes": [-7.2306 - 0.01], "longitudes": [-35.8811], "altitudes": [500]}}'
)


def test_recovers_the_call_observed_in_the_dashboard() -> None:
    buffer = ProposalBuffer()
    assert recover(buffer, OBSERVED_BLOB) is not None

    action = last_proposal(buffer)
    assert action.action_type == ActionType.ADD_NODES
    assert isinstance(action.payload, AddNodesPayload)
    assert abs(action.payload.nodes[0].lat - (-7.2406)) < 1e-6, "the arithmetic was not evaluated"


def test_a_call_that_went_through_is_not_reported_as_a_failure() -> None:
    """Observed 1 October 2026: the model called the tool properly *and*
    repeated the call as its whole reply. The proposal reached the gate while
    the message beside it told the operator nothing had been proposed."""
    buffer = ProposalBuffer()
    buffer.propose_run_simulation(steps=5)

    reply = answer_for_a_reply_that_is_a_call(buffer)

    assert "Advance simulation by 5 steps" in reply
    assert reply != UNUSABLE_TOOL_CALL_MESSAGE


def test_a_call_that_went_nowhere_still_asks_the_operator_to_rephrase() -> None:
    assert answer_for_a_reply_that_is_a_call(ProposalBuffer()) == UNUSABLE_TOOL_CALL_MESSAGE


def test_the_blob_itself_never_reaches_the_chat() -> None:
    """Whichever branch answers, the raw call must not be what the operator
    reads — that is the whole reason this replacement exists."""
    buffer = ProposalBuffer()
    buffer.propose_run_simulation(steps=5)

    for reply in (answer_for_a_reply_that_is_a_call(buffer), answer_for_a_reply_that_is_a_call(ProposalBuffer())):
        assert not looks_like_tool_call(reply)
        assert "propose_" not in reply


def test_plain_prose_is_not_mistaken_for_a_tool_call() -> None:
    assert parse_tool_call("There are 8 active satellites in the constellation.") is None
    assert not looks_like_tool_call("Ground Station 3 has no servers attached.")


def test_alternative_field_names_are_accepted() -> None:
    buffer = ProposalBuffer()
    assert recover(buffer, '{"tool": "propose_run_simulation", "arguments": {"steps": 4}}') is not None
    payload = last_proposal(buffer).payload
    assert isinstance(payload, RunSimulationPayload)
    assert payload.steps == 4


def test_a_call_embedded_in_surrounding_prose_is_found() -> None:
    buffer = ProposalBuffer()
    text = 'Sure, I will do that:\n{"name": "propose_run_simulation", "parameters": {"steps": 2}}\nConfirm below.'
    assert recover(buffer, text) is not None
    payload = last_proposal(buffer).payload
    assert isinstance(payload, RunSimulationPayload)
    assert payload.steps == 2


def test_code_in_the_payload_is_refused() -> None:
    """The evaluator accepts data and arithmetic; any call is refused."""
    hostile = '{"name": "propose_run_simulation", "parameters": {"steps": __import__("os").system("id")}}'
    assert parse_tool_call(hostile) is None


def test_unknown_tool_names_are_ignored() -> None:
    buffer = ProposalBuffer()
    assert recover(buffer, '{"name": "delete_everything", "parameters": {}}') is None
    assert buffer.get_proposals() == []


def test_wrong_arguments_do_not_raise() -> None:
    buffer = ProposalBuffer()
    result = recover(buffer, '{"name": "propose_run_simulation", "parameters": {"ticks": 3}}')
    assert result is not None
    assert result.startswith("Error:")
    assert buffer.get_proposals() == []
