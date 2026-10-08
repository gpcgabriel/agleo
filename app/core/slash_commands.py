"""Centralized slash command registry.

Single source of truth consumed both by the JavaScript autocomplete menu and
by the Python command router.
"""

from typing import TypedDict


class SlashCommand(TypedDict):
    """One command of the registry, as the autocomplete menu and the router read it."""

    # The command string, e.g. "/step ".
    cmd: str
    # A short human-readable description.
    desc: str
    # Whether the menu sends the command right after it is picked.
    auto_submit: bool
    # Whether the command is answered locally, without calling the agent.
    local: bool


SLASH_COMMANDS = [
    {
        "cmd": "/help",
        "desc": "List all available commands with descriptions",
        "auto_submit": True,
        "local": True,
    },
    {
        "cmd": "/step ",
        "desc": "Advance simulation by n steps (e.g., /step 5)",
        "auto_submit": False,
        "local": False,
    },
    {
        "cmd": "/restart",
        "desc": "Reset simulation back to Step 0",
        "auto_submit": True,
        "local": False,
    },
    {
        "cmd": "/review",
        "desc": "Analyze the network for issues or bottlenecks",
        "auto_submit": True,
        "local": False,
    },
]


def get_help_message() -> str:
    """
    Generates the /help response message listing all available commands.
    This is rendered directly in the chat without calling the LLM agent.
    """
    lines = ["### 🛰️ Available Slash Commands\n"]
    lines.append("Type `/` in the chat to see the autocomplete menu.\n")
    for entry in SLASH_COMMANDS:
        cmd_display = f"`{entry['cmd'].strip()}`"
        lines.append(f"*   **{cmd_display}** — {entry['desc']}")
    return "\n".join(lines)


def get_commands_for_js() -> list[dict[str, str | bool]]:
    """
    Returns the command list formatted for the frontend JS autocomplete menu.
    Output: list of {cmd, desc, autoSubmit}
    """
    return [
        {
            "cmd": c["cmd"],
            "desc": c["desc"],
            "autoSubmit": c["auto_submit"],
        }
        for c in SLASH_COMMANDS
    ]
