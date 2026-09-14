"""Routing of commands typed by the operator.

Decides what to do with a message before any inference: answer locally,
refuse, or forward it to the agent with the appropriate context.
"""

from app.core.slash_commands import SLASH_COMMANDS, get_help_message
from app.core.summary import summarize_snapshot

HELP_COMMANDS = ("/", "/help")
REVIEW_COMMAND = "/review"

QUICK_COMMAND_CONTEXT = (
    "Quick Command Mode (Slash Command). "
    "Execute the corresponding action immediately by calling the appropriate tool."
)

VIEWING_HISTORY_MESSAGE = (
    "⚠️ You are viewing a historical step. To send commands, drag the slider to the most recent step."
)
PENDING_ACTION_MESSAGE = (
    "⚠️ Resolve the pending proposed action in the upper panel before continuing the conversation."
)


class LocalReply:
    """A reply produced without consulting the agent."""

    def __init__(self, text):
        self.text = text


class Blocked:
    """A refusal: the command cannot be accepted in the current state."""

    def __init__(self, reason):
        self.reason = reason


class DispatchToAgent:
    """A forward to the agent, carrying the context it should receive."""

    def __init__(self, context_state):
        self.context_state = context_state


def is_known_command(prompt):
    """Returns: bool: True if the text starts with a registered command."""
    stripped = prompt.strip()
    return any(stripped.startswith(entry["cmd"].strip()) for entry in SLASH_COMMANDS)


def build_agent_context(prompt, snapshot):
    """Builds the context injected into the agent's prompt.

    Slash commands get a minimal context, because the action is already
    determined; natural-language questions get the detailed state.

    Args:
        prompt (str): The operator's command.
        snapshot (dict): The snapshot currently on screen.

    Returns:
        str: Context to send to the agent.
    """
    if prompt.startswith("/") and not prompt.lower().startswith(REVIEW_COMMAND):
        return QUICK_COMMAND_CONTEXT

    return (
        "You have access to the current detailed simulation state below:\n\n"
        f"{summarize_snapshot(snapshot)}\n\n"
        "Use this data to answer informational questions. "
        "If the operator explicitly requests a change or advancement to the simulation "
        "in natural language, you MUST use the appropriate tool to propose the action."
    )


def route(prompt, session, has_pending_action):
    """Decides where a command from the operator goes.

    Args:
        prompt (str): The text typed.
        session (SimulationSession): Active simulation.
        has_pending_action (bool): Whether a proposal awaits a decision.

    Returns:
        LocalReply, Blocked or DispatchToAgent: The decision taken.
    """
    stripped = prompt.strip()

    if stripped.lower() in HELP_COMMANDS:
        return LocalReply(get_help_message())

    if stripped.startswith("/") and not is_known_command(stripped):
        return LocalReply(f"**Unknown command:** `{stripped}`\n\n{get_help_message()}")

    # The history check comes first: telling someone to resolve a proposal
    # they cannot even see would be confusing.
    if not session.is_viewing_latest():
        return Blocked(VIEWING_HISTORY_MESSAGE)

    if has_pending_action:
        return Blocked(PENDING_ACTION_MESSAGE)

    return DispatchToAgent(build_agent_context(prompt, session.get_current_snapshot()))
