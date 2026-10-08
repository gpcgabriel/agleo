"""Helpers the tests share to read what the agent's tools proposed."""

from app.agents.dashboard.tools import ProposalBuffer
from app.core.actions import ProposedAction


def last_proposal(buffer: ProposalBuffer) -> ProposedAction:
    """Returns: ProposedAction: The buffer's latest proposal, failing the test when there is none."""
    proposal = buffer.get_last_proposal()
    if proposal is None:
        raise AssertionError("no proposal was registered")
    return proposal
