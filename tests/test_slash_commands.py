"""Tests for the centralized slash command registry.

`SLASH_COMMANDS` is read by three consumers that cannot see each other: the
router, the help message and the JavaScript autocomplete menu inside
`accessibility.js`. A command added in one shape and consumed in another fails
only in the browser, which is why the registry is checked here rather than at
each consumer.

This was one 75-line test wrapped in a hand-rolled stdout capture that printed
its own SUCCESS line and bypassed `run_module_tests`; a failure named nothing.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.slash_commands import SLASH_COMMANDS, get_commands_for_js, get_help_message

REQUIRED_KEYS = ("cmd", "desc", "auto_submit", "local")


def test_every_command_carries_the_keys_its_consumers_read():
    for command in SLASH_COMMANDS:
        for key in REQUIRED_KEYS:
            assert key in command, f"{command.get('cmd', command)} has no {key!r}"


def test_help_is_registered_and_answered_without_the_agent():
    """`/help` is the one command the router answers locally; if the registry
    stops saying so, it goes to the model and costs a round trip."""
    help_command = next((c for c in SLASH_COMMANDS if c["cmd"] == "/help"), None)

    assert help_command is not None
    assert help_command["local"] is True


def test_the_help_message_mentions_every_command():
    """A command absent from the help message exists only for whoever already
    knows it is there."""
    message = get_help_message()

    for command in SLASH_COMMANDS:
        assert command["cmd"].strip() in message, f"{command['cmd']} is missing from the help message"


def test_the_javascript_menu_offers_the_same_commands_in_its_own_shape():
    """`accessibility.js` reads `autoSubmit`, not `auto_submit`."""
    for_js = get_commands_for_js()

    assert len(for_js) == len(SLASH_COMMANDS)
    for command in for_js:
        for key in ("cmd", "desc", "autoSubmit"):
            assert key in command, f"{command.get('cmd', command)} has no {key!r}"


def test_the_menu_survives_the_trip_into_javascript():
    """It is interpolated into the script as JSON, so a value that cannot be
    serialized breaks the slash menu and nothing else, silently."""
    serialized = json.dumps(get_commands_for_js(), ensure_ascii=False)

    assert json.loads(serialized) == get_commands_for_js()


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
