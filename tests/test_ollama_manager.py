"""Tests for the Ollama helper.

These are the only tests in the project that mock anything, because the
alternative is starting and stopping a daemon. They ran nowhere until
30 September 2026: the module had no `__main__` block, so the sweep skipped it,
and three of them patched `gui.ollama_manager`, a package that stopped existing
in Phase 1.

Patching is done with `with` blocks rather than stacked decorators: the
decorator form injects one mock per decorator in reverse order, which is
exactly the kind of implicit wiring this project avoids.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.helper_functions.ollama_helper import (
    DEFAULT_HOST,
    is_ollama_running,
    list_local_models,
    pull_model,
    start_ollama,
)

HELPER = "app.helper_functions.ollama_helper"


def respond_with(status_code, payload=None):
    """Returns: MagicMock: A response object shaped like `requests` returns."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    return response


# -- Reaching the daemon ----------------------------------------------------


def test_the_daemon_is_running_when_the_tags_endpoint_answers():
    with patch("requests.get", return_value=respond_with(200)) as mock_get:
        assert is_ollama_running() is True
        mock_get.assert_called_once_with(f"{DEFAULT_HOST}/api/tags", timeout=2)


def test_a_refused_connection_means_the_daemon_is_not_running():
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
        assert is_ollama_running() is False


def test_an_error_status_means_the_daemon_is_not_running():
    """Something answering on the port is not the same as Ollama answering."""
    with patch("requests.get", return_value=respond_with(500)):
        assert is_ollama_running() is False


# -- Starting it ------------------------------------------------------------


def test_a_daemon_already_running_is_not_started_twice():
    with patch(f"{HELPER}.is_ollama_running", return_value=True):
        with patch("subprocess.Popen") as mock_popen:
            assert start_ollama() is True
            mock_popen.assert_not_called()


def test_the_daemon_is_started_and_waited_for():
    with patch(f"{HELPER}.is_ollama_running", side_effect=[False, True]):
        with patch("subprocess.Popen") as mock_popen, patch("time.sleep"):
            assert start_ollama() is True
            mock_popen.assert_called_once()


def test_a_daemon_that_never_answers_gives_up_instead_of_hanging():
    """Twenty polls at half a second: ten seconds, then False."""
    with patch(f"{HELPER}.is_ollama_running", return_value=False):
        with patch("subprocess.Popen") as mock_popen, patch("time.sleep") as mock_sleep:
            assert start_ollama() is False
            mock_popen.assert_called_once()
            assert mock_sleep.call_count == 20


# -- Listing what is installed ----------------------------------------------


def test_the_local_models_come_back_by_name():
    payload = {"models": [{"name": "llama3.1:latest"}, {"name": "gemma:latest"}]}

    with patch("requests.get", return_value=respond_with(200, payload)):
        assert list_local_models() == ["llama3.1:latest", "gemma:latest"]


def test_a_model_entry_without_a_name_is_left_out():
    """The response shape has changed before; a missing key must not raise."""
    payload = {"models": [{"name": "llama3.1:latest"}, {"model": "gemma:latest"}]}

    with patch("requests.get", return_value=respond_with(200, payload)):
        assert list_local_models() == ["llama3.1:latest"]


def test_an_unreachable_daemon_lists_nothing_rather_than_raising():
    with patch("requests.get", side_effect=Exception("HTTP Error")):
        assert list_local_models() == []


# -- Downloading one --------------------------------------------------------


def test_a_download_reports_every_line_it_printed():
    process = MagicMock()
    process.poll.side_effect = [None, None, 0]
    process.stdout.readline.side_effect = ["downloading layer 1\n", "downloading layer 2\n", "", "", ""]
    # Faking returncode as a property, which a plain attribute cannot do.
    type(process).returncode = property(lambda self: 0)

    reported = []
    with patch("subprocess.Popen", return_value=process):
        assert pull_model("llama3.1", progress_callback=reported.append) is True

    assert reported == ["downloading layer 1", "downloading layer 2"]


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
