"""Prompt construction for the allocation agent."""

from json import dumps

HISTORY_STEPS_SHOWN = 5

INSTRUCTIONS = [
    "You allocate applications in a LEO satellite network.",
    "Objective: maximize the number of provisioned applications.",
    "Choose one strategy per application, from two options.",
    "best_fit: packs an application into the tightest-fitting process unit, " "minimizing wasted resources.",
    "longest_duration: picks the satellite with the longest remaining visibility " "time for the user.",
    "Every pending application ID must appear in exactly one of the two lists.",
]


def build_history_section(decisions):
    """Summarizes recent decisions and how they turned out.

    Args:
        decisions (list): Past entries for one ground station.

    Returns:
        str: The section to append to the prompt, empty when there is no history.
    """
    if not decisions:
        return ""

    lines = ["\n=== Past decisions (most recent first) ==="]
    for entry in decisions[-HISTORY_STEPS_SHOWN:]:
        results = entry["results"]
        lines.append(
            f"Step {entry['step']}: best_fit={entry['best_fit']} "
            f"longest_duration={entry['longest_duration']} "
            f"-> provisioned={results.get('provisioned', 0)} failed={results.get('failed', 0)}"
        )

    return "\n".join(lines) + "\n"


def build_allocation_prompt(state, pending_app_ids, decisions):
    """Builds the prompt for one allocation decision.

    Args:
        state (dict): The trimmed network state.
        pending_app_ids (list): Applications waiting for placement.
        decisions (list): Past decisions of this ground station.

    Returns:
        str: The prompt to send to the agent.
    """
    return (
        f"PENDING APPS (IDs to allocate): {pending_app_ids}\n"
        f"Network State (JSON):\n{dumps(state, default=str)}\n"
        f"{build_history_section(decisions)}"
    )
