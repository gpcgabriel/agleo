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

from unittest.mock import MagicMock, patch

import requests
from ollama import ProgressResponse, ResponseError

from app.helper_functions.ollama_helper import (
    DEFAULT_HOST,
    is_ollama_running,
    list_local_models,
    pull_model,
    start_ollama,
)

HELPER = "app.helper_functions.ollama_helper"


def respond_with(status_code: int, payload: object = None) -> MagicMock:
    """Returns: MagicMock: A response object shaped like `requests` returns."""
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload or {}
    return response


# -- Reaching the daemon ----------------------------------------------------


def test_the_daemon_is_running_when_the_tags_endpoint_answers() -> None:
    with patch("requests.get", return_value=respond_with(200)) as mock_get:
        assert is_ollama_running() is True
        mock_get.assert_called_once_with(f"{DEFAULT_HOST}/api/tags", timeout=2)


def test_a_refused_connection_means_the_daemon_is_not_running() -> None:
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
        assert is_ollama_running() is False


def test_an_error_status_means_the_daemon_is_not_running() -> None:
    """Something answering on the port is not the same as Ollama answering."""
    with patch("requests.get", return_value=respond_with(500)):
        assert is_ollama_running() is False


# -- Starting it ------------------------------------------------------------


def test_a_daemon_already_running_is_not_started_twice() -> None:
    with patch(f"{HELPER}.is_ollama_running", return_value=True), patch("subprocess.Popen") as mock_popen:
        assert start_ollama() is True
        mock_popen.assert_not_called()


def test_the_daemon_is_started_and_waited_for() -> None:
    with (
        patch(f"{HELPER}.is_ollama_running", side_effect=[False, True]),
        patch("subprocess.Popen") as mock_popen,
        patch("time.sleep"),
    ):
        assert start_ollama() is True
        mock_popen.assert_called_once()


def test_a_daemon_that_never_answers_gives_up_instead_of_hanging() -> None:
    """Twenty polls at half a second: ten seconds, then False."""
    with (
        patch(f"{HELPER}.is_ollama_running", return_value=False),
        patch("subprocess.Popen") as mock_popen,
        patch("time.sleep") as mock_sleep,
    ):
        assert start_ollama() is False
        mock_popen.assert_called_once()
        assert mock_sleep.call_count == 20


# -- Listing what is installed ----------------------------------------------


def test_the_local_models_come_back_by_name() -> None:
    payload = {"models": [{"name": "llama3.1:latest"}, {"name": "gemma:latest"}]}

    with patch("requests.get", return_value=respond_with(200, payload)):
        assert list_local_models() == ["llama3.1:latest", "gemma:latest"]


def test_a_model_entry_without_a_name_is_left_out() -> None:
    """The response shape has changed before; a missing key must not raise."""
    payload = {"models": [{"name": "llama3.1:latest"}, {"model": "gemma:latest"}]}

    with patch("requests.get", return_value=respond_with(200, payload)):
        assert list_local_models() == ["llama3.1:latest"]


def test_an_unreachable_daemon_lists_nothing_rather_than_raising() -> None:
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError()):
        assert list_local_models() == []


def test_a_reply_shaped_unlike_a_model_list_raises_instead_of_listing_nothing() -> None:
    """Only an unreachable daemon means "no models". A reply in a shape this code does not
    expect is a fault to surface, not an empty list to show the operator."""
    with patch("requests.get", return_value=respond_with(200, ["llama3.1:latest"])):
        try:
            list_local_models()
        except AttributeError:
            return
    raise AssertionError("a reply that is not a model list was read as an empty one")


# -- Downloading one --------------------------------------------------------


def pulling(*updates: ProgressResponse) -> MagicMock:
    """Returns: MagicMock: A client whose download streams the given updates."""
    client = MagicMock()
    client.pull.return_value = iter(updates)
    return client


def test_a_download_reports_every_progress_update() -> None:
    """The size is known for a layer, so its line carries a percentage; a step without one does not."""
    client = pulling(
        ProgressResponse(status="pulling manifest"),
        ProgressResponse(status="pulling 667b0c1932bc", total=200, completed=50),
        ProgressResponse(status="success"),
    )

    reported = []
    with patch("ollama.Client", return_value=client):
        assert pull_model("llama3.1", progress_callback=reported.append) is True

    assert reported == ["pulling manifest", "pulling 667b0c1932bc 25%", "success"]


def test_a_download_ollama_refuses_reports_a_failure() -> None:
    client = MagicMock()
    client.pull.side_effect = ResponseError("pull model manifest: file does not exist")

    with patch("ollama.Client", return_value=client):
        assert pull_model("no-such-model") is False


def test_a_download_with_the_daemon_down_reports_a_failure() -> None:
    client = MagicMock()
    client.pull.side_effect = ConnectionError("Failed to connect to Ollama.")

    with patch("ollama.Client", return_value=client):
        assert pull_model("llama3.1") is False
