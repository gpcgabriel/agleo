"""Helpers the tests share to call the agent's tools and read what they proposed."""

from app.agents.dashboard.tools import ProposalBuffer
from app.core.actions import ProposedAction


def propose_nodes(buffer: ProposalBuffer, *arguments: object) -> str:
    """Calls the add-node tool as the model would.

    Its parameters stay unannotated on purpose (see `ProposalBuffer.propose_add_node`), which leaves
    the call untyped; this is the one place in the tests that says so.
    """
    return buffer.propose_add_node(*arguments)  # pyright: ignore[reportUnknownMemberType]


def last_proposal(buffer: ProposalBuffer) -> ProposedAction:
    """Returns: ProposedAction: The buffer's latest proposal, failing the test when there is none."""
    proposal = buffer.get_last_proposal()
    if proposal is None:
        raise AssertionError("no proposal was registered")
    return proposal
