"""The agent that stands between the operator and the simulation.

It never mutates the engine. Its tools record typed proposals in a
`ProposalBuffer` scoped to one run, and the interface renders the confirmation
gate that turns a proposal into a change.
"""

from app.agents.dashboard.runner import MODE_SKILLS, MODE_TOOLS, run_agent

__all__ = ["MODE_SKILLS", "MODE_TOOLS", "run_agent"]
