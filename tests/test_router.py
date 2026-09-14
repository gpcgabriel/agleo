"""Tests for command routing.

Routing is a pure function, testable without the interface and without model
inference.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.router import Blocked, DispatchToAgent, LocalReply, QUICK_COMMAND_CONTEXT, route


class FakeSession:
    """Minimal session exposing what the router reads."""

    def __init__(self, viewing_latest=True, snapshot=None):
        self.viewing_latest = viewing_latest
        self.snapshot = snapshot or {
            "step": 0,
            "satellites": [],
            "ground_stations": [],
            "users": [],
            "links": [],
        }

    def is_viewing_latest(self):
        return self.viewing_latest

    def get_current_snapshot(self):
        return self.snapshot


def test_help_is_answered_locally_without_calling_the_agent():
    for prompt in ("/help", "/", "  /HELP  "):
        decision = route(prompt, FakeSession(), has_pending_action=False)
        assert isinstance(decision, LocalReply), prompt
        assert "Available Slash Commands" in decision.text


def test_an_unknown_slash_command_is_answered_locally():
    decision = route("/teleport", FakeSession(), has_pending_action=False)

    assert isinstance(decision, LocalReply)
    assert "Unknown command" in decision.text


def test_commands_are_blocked_while_viewing_history():
    decision = route("/step 5", FakeSession(viewing_latest=False), has_pending_action=False)

    assert isinstance(decision, Blocked)
    assert "historical step" in decision.reason


def test_commands_are_blocked_while_a_proposal_is_pending():
    decision = route("/step 5", FakeSession(), has_pending_action=True)

    assert isinstance(decision, Blocked)
    assert "pending proposed action" in decision.reason


def test_a_slash_command_reaches_the_agent_with_the_short_context():
    decision = route("/step 5", FakeSession(), has_pending_action=False)

    assert isinstance(decision, DispatchToAgent)
    assert decision.context_state == QUICK_COMMAND_CONTEXT


def test_review_reaches_the_agent_with_the_detailed_state():
    decision = route("/review", FakeSession(), has_pending_action=False)

    assert isinstance(decision, DispatchToAgent)
    assert "Simulation State Information" in decision.context_state


def test_a_natural_language_question_reaches_the_agent_with_the_detailed_state():
    decision = route("how many users are connected?", FakeSession(), has_pending_action=False)

    assert isinstance(decision, DispatchToAgent)
    assert "Simulation State Information" in decision.context_state


def test_history_is_checked_before_the_pending_proposal():
    """Someone looking at the past needs to hear that first: being told to
    resolve a proposal they cannot even see would be confusing."""
    decision = route("/step 5", FakeSession(viewing_latest=False), has_pending_action=True)

    assert isinstance(decision, Blocked)
    assert "historical step" in decision.reason


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
