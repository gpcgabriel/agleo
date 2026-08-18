import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.helper_functions.slash_commands import SLASH_COMMANDS, get_help_message, get_commands_for_js


def test_slash_commands_registry():
    """Validates the centralized slash command registry structure and outputs."""
    import io
    from contextlib import contextmanager

    @contextmanager
    def capture_output(test_name):
        buffer = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = buffer
        sys.stderr = buffer
        try:
            yield buffer
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            print(f"=> {test_name}: SUCCESS")
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            print(buffer.getvalue(), end="")
            raise e

    with capture_output("test_slash_commands_registry"):
        # All commands must have required keys
        for cmd in SLASH_COMMANDS:
            assert "cmd" in cmd, f"Missing 'cmd' key in {cmd}"
            assert "desc" in cmd, f"Missing 'desc' key in {cmd}"
            assert "auto_submit" in cmd, f"Missing 'auto_submit' key in {cmd}"
            assert "local" in cmd, f"Missing 'local' key in {cmd}"
        print(f"Registry has {len(SLASH_COMMANDS)} commands, all with valid keys.")

        # /help must exist and be local
        help_cmd = next((c for c in SLASH_COMMANDS if c["cmd"] == "/help"), None)
        assert help_cmd is not None, "/help command not found in registry"
        assert help_cmd["local"] is True, "/help must be a local command"
        print("/help found and marked as local.")

        # get_help_message must mention all commands
        help_msg = get_help_message()
        assert isinstance(help_msg, str)
        assert len(help_msg) > 0
        for cmd in SLASH_COMMANDS:
            cmd_stripped = cmd["cmd"].strip()
            assert cmd_stripped in help_msg, f"Command '{cmd_stripped}' not found in help message"
        print("get_help_message() includes all commands.")

        # get_commands_for_js must return proper structure
        js_cmds = get_commands_for_js()
        assert len(js_cmds) == len(SLASH_COMMANDS)
        for jc in js_cmds:
            assert "cmd" in jc, f"Missing 'cmd' in JS command: {jc}"
            assert "desc" in jc, f"Missing 'desc' in JS command: {jc}"
            assert "autoSubmit" in jc, f"Missing 'autoSubmit' in JS command: {jc}"
        print("get_commands_for_js() returns correct structure.")

        # Verify JSON serialization works (no circular refs, no non-serializable types)
        import json

        serialized = json.dumps(js_cmds, ensure_ascii=False)
        assert len(serialized) > 10
        print(f"JSON serialization OK ({len(serialized)} chars).")


if __name__ == "__main__":
    test_slash_commands_registry()
