"""
Centralized Slash Command registry for LEOSim.
Single source of truth consumed by both frontend (JS autocomplete menu)
and backend (Python command router in app.py).
"""

# Each command is a dict with these keys:
#   cmd: str          — The slash command string (e.g. "/step ")
#   desc: str         — Short human-readable description
#   auto_submit: bool — If True, the JS menu auto-clicks send after selection
#   local: bool       — If True, command is handled locally (no agent call)

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


def get_commands_for_js() -> list[dict]:
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
