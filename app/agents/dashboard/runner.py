"""Assembly and execution of the dashboard agent."""

import json
import logging
import os
import sys

from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.skills import LocalSkills, Skills

from app.agents.dashboard.prompts import dashboard_agent_description, dashboard_agent_instructions
from app.agents.dashboard.tool_call_recovery import looks_like_tool_call, recover
from app.agents.dashboard.tools import ProposalBuffer
from app.core.actions import ProposedAction, build_payload

logger = logging.getLogger(__name__)

# Ollama defaults this model to 4096 tokens, and the dashboard prompt does not
# fit: the state summary is ~2 500 tokens on the default scenario, the tool
# schemas another ~640, and Skills adds agno's scaffold on top — one run
# measured 5 176 input tokens. Everything past the window is dropped silently,
# so the agent was answering half a question. The allocation agent has carried
# this setting since Phase 3; this one was missing it.
DEFAULT_CONTEXT_SIZE = 8192

MODE_TOOLS = "Tools"
MODE_SKILLS = "Skills"

# Resolved against this package rather than the working directory: Streamlit is
# launched from wherever the operator happens to be.
SKILLS_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills")


# The agno tool a skill script arrives through.
SKILL_SCRIPT_TOOL = "get_skill_script"

UNUSABLE_TOOL_CALL_MESSAGE = (
    "I tried to issue that command but produced a malformed tool call, so nothing was "
    "proposed. Please rephrase the request — for example, state the coordinates explicitly."
)


class AgentResult:
    """Outcome of one agent run.

    Keeps the two outputs apart: the text shown to the operator, and the
    proposals recorded by the tools.
    """

    def __init__(self, text, proposals, usage=None):
        """Args:
        text (str): The agent's natural-language reply.
        proposals (list): Proposals recorded during the run.
        usage (dict): Tokens the run consumed, or None when the model did not
            report them. The interface ignores this; it exists because
            comparing the two capability models means counting what each one
            costs per command, and the alternative is a second copy of this
            pipeline in the measurement script.
        """
        self.text = text
        self.proposals = list(proposals)
        self.usage = usage or {}

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


def ensure_interpreter_on_path():
    """Puts the running interpreter first on PATH for child processes.

    A skill script is executed directly through its shebang, which reads
    `#!/usr/bin/env python3`. On a machine where Python is managed by pyenv or
    uv, the `python3` that resolves to is the system one, and the script dies
    importing what only the environment has. Prepending this interpreter's own
    directory makes the subprocess run under the same Python the dashboard does.
    """
    directory = os.path.dirname(sys.executable)
    parts = os.environ.get("PATH", "").split(os.pathsep)

    if parts and parts[0] == directory:
        return

    os.environ["PATH"] = os.pathsep.join([directory] + [part for part in parts if part != directory])


def build_agent(model_name, action_mode, buffer, skills_directory=None):
    """Assembles the dashboard agent.

    Args:
        model_name (str): Model identifier in Ollama.
        action_mode (str): MODE_TOOLS, MODE_SKILLS, or None to disable actions
            and leave the agent informational only.
        buffer (ProposalBuffer): Buffer that will receive the proposals.
        skills_directory (str): Which skill tree to load in Skills mode.
            Defaults to `SKILLS_DIRECTORY`.

    Returns:
        Agent: The configured agent.

    Raises:
        ValueError: If `action_mode` is not recognized.
    """
    model = Ollama(id=model_name, options={"temperature": 0.1, "num_ctx": DEFAULT_CONTEXT_SIZE})
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
        ensure_interpreter_on_path()

        # No `propose_*` tools here, deliberately. The two modes are the two
        # capability models being compared: six tool schemas in the system
        # prompt against progressive disclosure, where the model sees a short
        # skill description and opens the rest only when it decides the skill
        # applies. Giving this mode the tools as well would compare nothing.
        return Agent(
            model=model,
            description=description,
            instructions=instructions,
            skills=Skills(loaders=[LocalSkills(skills_directory or SKILLS_DIRECTORY)]),
        )

    raise ValueError(f"Invalid action_mode: {action_mode!r}. Expected {MODE_TOOLS!r}, {MODE_SKILLS!r} or None.")


def collect_script_proposals(response, buffer):
    """Records the proposals a skill script printed.

    A skill script runs as a subprocess, so it cannot reach the buffer the way
    a tool does. It prints the action and its arguments instead, and this
    rebuilds the payload in this process and registers it.

    Args:
        response (RunOutput): What the agent returned.
        buffer (ProposalBuffer): Buffer that receives the proposals.

    Returns:
        int: How many proposals were recorded.
    """
    recorded = 0

    for execution in getattr(response, "tools", None) or []:
        if getattr(execution, "tool_name", None) != SKILL_SCRIPT_TOOL:
            continue

        try:
            printed = json.loads(getattr(execution, "result", "") or "")
            proposal = json.loads(printed.get("stdout", "")).get("proposal")
        except (TypeError, ValueError, AttributeError):
            logger.debug("Skill script produced no readable proposal: %r", getattr(execution, "result", None))
            continue

        if not proposal:
            continue

        try:
            # Passing the configuration in use: restarting is resolved against
            # it, and a subprocess has no way to see it.
            payload = build_payload(
                proposal["action_type"], proposal["arguments"], current_config=buffer.current_config
            )
            buffer.register(ProposedAction(proposal["action_type"], payload))
            recorded += 1
        except (KeyError, TypeError, ValueError) as error:
            logger.warning("Skill script proposed something invalid: %s", error)

    return recorded


def read_usage(response):
    """Reads the token counts off a run, tolerating a model that omits them.

    Args:
        response (RunOutput): What the agent returned.

    Returns:
        dict: "input_tokens" and "output_tokens", zero when unreported.
    """
    metrics = getattr(response, "metrics", None)

    return {
        "input_tokens": getattr(metrics, "input_tokens", 0) or 0,
        "output_tokens": getattr(metrics, "output_tokens", 0) or 0,
    }


def run_agent(
    prompt,
    model_name,
    action_mode,
    context_state,
    current_config=None,
    default_position=None,
    skills_directory=None,
):
    """Runs the agent for one operator command.

    Args:
        prompt (str): Command typed by the operator.
        model_name (str): Model identifier in Ollama.
        action_mode (str): MODE_TOOLS, MODE_SKILLS, or None.
        context_state (str): Simulation state summary injected into the prompt.
        current_config (SimulationConfig): Active configuration, used as the
            base by proposals that change only part of the parameters.
        default_position (tuple): (latitude, longitude) for a node the operator
            did not place.
        skills_directory (str): Which skill tree to load in Skills mode.

    Returns:
        AgentResult: Reply text and recorded proposals.
    """
    buffer = ProposalBuffer(current_config=current_config, default_position=default_position)
    agent = build_agent(model_name, action_mode, buffer, skills_directory=skills_directory)
    response = agent.run(f"Context state: {context_state}\n\nOperator Command: {prompt}")

    text = response.content or ""

    if action_mode == MODE_SKILLS:
        collect_script_proposals(response, buffer)

    # Recovering a tool call written into the reply body: small local models
    # sometimes do that instead of emitting it through the tool channel. Ollama
    # then has nothing to execute, and without this the operator would see the
    # raw dictionary in the chat.
    #
    # It was off while Tools and Skills were being compared: the net turned
    # calls the model wrote as text into proposals, which made a mode that
    # never opened a skill look like it worked. The comparison is closed, so it
    # is back on — Tools reaches the gate on its own, and this only catches the
    # replies where it does not.
    if not buffer.get_proposals():
        recovered = recover(buffer, text)
        if recovered is not None:
            text = recovered

    if looks_like_tool_call(text):
        text = UNUSABLE_TOOL_CALL_MESSAGE

    return AgentResult(text=text, proposals=buffer.get_proposals(), usage=read_usage(response))
