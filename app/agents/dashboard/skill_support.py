"""Shared plumbing for the skill scripts.

Each skill owns one action and one script. The scripts are tiny on purpose:
what distinguishes them is the `SKILL.md` beside them, which is the context the
agent reads only when it judges that skill relevant. Everything mechanical —
finding the repository, validating, printing — lives here so a skill folder is
a description and a command line, not a program.
"""

import json

from app.core.actions import ACTIONS_NEEDING_CURRENT_CONFIG, build_payload


def emit(action_type, arguments, summary=""):
    """Prints one proposal as JSON, or the reason it could not be built.

    The script runs as a subprocess and cannot reach the proposal buffer, so
    `runner.collect_script_proposals` reads this back and rebuilds the payload
    in the dashboard's own process.

    Args:
        action_type (str): The action this skill proposes.
        arguments (dict): Fields for that action.
        summary (str): Description to print for an action whose payload cannot
            be built here. Restarting is the one: its settings are resolved
            against the configuration currently loaded, which only the
            dashboard's process holds, so the values are validated when the
            runner completes them rather than now.

    Returns:
        int: 0 when a proposal was produced, 1 otherwise.
    """
    if action_type in ACTIONS_NEEDING_CURRENT_CONFIG:
        print(
            json.dumps(
                {
                    "proposal": {
                        "action_type": action_type,
                        "arguments": arguments,
                        "description": summary,
                        "chosen_automatically": "",
                    }
                }
            )
        )
        return 0

    try:
        payload = build_payload(action_type, arguments)
    except (ValueError, TypeError, KeyError) as error:
        print(json.dumps({"error": str(error)}))
        return 1

    print(
        json.dumps(
            {
                "proposal": {
                    "action_type": action_type,
                    "arguments": arguments,
                    "description": payload.describe(),
                    # Kept out of the description so it never comes back as an argument.
                    "chosen_automatically": (
                        payload.describe_defaults() if hasattr(payload, "describe_defaults") else ""
                    ),
                }
            }
        )
    )
    return 0


def run(action_type, parser, collect, summarize=None):
    """Parses the command line and emits the proposal it describes.

    Args:
        action_type (str): The action this skill proposes.
        parser (argparse.ArgumentParser): The script's command line.
        collect (Callable): Turns parsed arguments into the payload's fields.
        summarize (Callable): Turns those fields into a description, for an
            action whose payload this process cannot build.

    Returns:
        int: Exit status for the script.
    """
    args = parser.parse_args()

    try:
        arguments = collect(args)
    except (ValueError, TypeError) as error:
        print(json.dumps({"error": str(error)}))
        return 1

    return emit(action_type, arguments, summarize(arguments) if summarize else "")
