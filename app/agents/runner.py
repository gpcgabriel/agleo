"""Assembly and execution of the dashboard agent."""

from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.skills import LocalSkills, Skills

from app.agents.prompts import dashboard_agent_description, dashboard_agent_instructions
from app.agents.tool_call_recovery import looks_like_tool_call, recover
from app.agents.tools import ProposalBuffer

MODE_TOOLS = "Tools"
MODE_SKILLS = "Skills"

UNUSABLE_TOOL_CALL_MESSAGE = (
    "I tried to issue that command but produced a malformed tool call, so nothing was "
    "proposed. Please rephrase the request — for example, state the coordinates explicitly."
)


class AgentResult:
    """Outcome of one agent run.

    Keeps the two outputs apart: the text shown to the operator, and the
    proposals recorded by the tools.
    """

    def __init__(self, text, proposals):
        """Args:
            text (str): The agent's natural-language reply.
            proposals (list): Proposals recorded during the run.
        """
        self.text = text
        self.proposals = list(proposals)

    def has_proposals(self):
        """Returns: bool: True if the agent proposed at least one action."""
        return len(self.proposals) > 0

    def get_primary_proposal(self):
        """The proposal that should go to the confirmation gate.

        Returns:
            ProposedAction or None: The most recent proposal, or None.
        """
        if not self.proposals:
            return None
        return self.proposals[-1]


def build_agent(model_name, action_mode, buffer):
    """Assembles the dashboard agent.

    Args:
        model_name (str): Model identifier in Ollama.
        action_mode (str): MODE_TOOLS, MODE_SKILLS, or None to disable actions
            and leave the agent informational only.
        buffer (ProposalBuffer): Buffer that will receive the proposals.

    Returns:
        Agent: The configured agent.

    Raises:
        ValueError: If `action_mode` is not recognized.
    """
    model = Ollama(id=model_name, options={"temperature": 0.1})
    description = dashboard_agent_description()
    instructions = dashboard_agent_instructions()

    if action_mode is None:
        return Agent(model=model, description=description, instructions=instructions)

    if action_mode == MODE_TOOLS:
        return Agent(
            model=model,
            description=description,
            instructions=instructions,
            tools=buffer.get_tools(),
        )

    if action_mode == MODE_SKILLS:
        return Agent(
            model=model,
            description=description,
            instructions=instructions,
            skills=Skills(local_skills=LocalSkills()),
        )

    raise ValueError(f"Invalid action_mode: {action_mode!r}. Expected {MODE_TOOLS!r}, {MODE_SKILLS!r} or None.")


def run_agent(prompt, model_name, action_mode, context_state, current_config=None):
    """Runs the agent for one operator command.

    Args:
        prompt (str): Command typed by the operator.
        model_name (str): Model identifier in Ollama.
        action_mode (str): MODE_TOOLS, MODE_SKILLS, or None.
        context_state (str): Simulation state summary injected into the prompt.
        current_config (SimulationConfig): Active configuration, used as the
            base by proposals that change only part of the parameters.

    Returns:
        AgentResult: Reply text and recorded proposals.
    """
    buffer = ProposalBuffer(current_config=current_config)
    agent = build_agent(model_name, action_mode, buffer)
    response = agent.run(f"Context state: {context_state}\n\nOperator Command: {prompt}")

    text = response.content or ""

    # Small local models sometimes write the tool call into the body of the
    # reply instead of emitting it through the tool channel. Ollama then has
    # nothing to execute, and without this recovery the operator would see the
    # raw dictionary in the chat.
    if not buffer.get_proposals():
        recovered = recover(buffer, text)
        if recovered is not None:
            text = recovered

    if looks_like_tool_call(text):
        text = UNUSABLE_TOOL_CALL_MESSAGE

    return AgentResult(text=text, proposals=buffer.get_proposals())
