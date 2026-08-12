import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gui.ollama_manager import (
    is_ollama_running,
    start_ollama,
    list_local_models,
    pull_model,
    DEFAULT_MODEL
)

@patch("requests.get")
def test_is_ollama_running_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_get.return_value = mock_response

    assert is_ollama_running() is True
    mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=2)

@patch("requests.get")
def test_is_ollama_running_failure(mock_get):
    import requests
    mock_get.side_effect = requests.exceptions.ConnectionError()

    assert is_ollama_running() is False

@patch("requests.get")
def test_is_ollama_running_bad_status(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_get.return_value = mock_response

    assert is_ollama_running() is False

@patch("gui.ollama_manager.is_ollama_running")
def test_start_ollama_already_running(mock_running):
    mock_running.return_value = True

    assert start_ollama() is True

@patch("gui.ollama_manager.is_ollama_running")
@patch("subprocess.Popen")
@patch("time.sleep")
def test_start_ollama_success(mock_sleep, mock_popen, mock_running):
    # First check: False, subsequent checks: True
    mock_running.side_effect = [False, True]
    
    mock_process = MagicMock()
    mock_popen.return_value = mock_process

    assert start_ollama() is True
    mock_popen.assert_called_once()
    mock_running.assert_called()

@patch("gui.ollama_manager.is_ollama_running")
@patch("subprocess.Popen")
@patch("time.sleep")
def test_start_ollama_timeout(mock_sleep, mock_popen, mock_running):
    # Always return False for running
    mock_running.return_value = False
    
    mock_process = MagicMock()
    mock_popen.return_value = mock_process

    assert start_ollama() is False
    mock_popen.assert_called_once()
    assert mock_sleep.call_count == 20

@patch("requests.get")
def test_list_local_models_success(mock_get):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {"name": "llama3.1:latest", "model": "llama3.1:latest"},
            {"name": "gemma:latest", "model": "gemma:latest"}
        ]
    }
    mock_get.return_value = mock_response

    models = list_local_models()
    assert models == ["llama3.1:latest", "gemma:latest"]

@patch("requests.get")
def test_list_local_models_failure(mock_get):
    mock_get.side_effect = Exception("HTTP Error")
    assert list_local_models() == []

@patch("subprocess.Popen")
def test_pull_model_success(mock_popen):
    mock_process = MagicMock()
    mock_process.poll.side_effect = [None, None, 0]
    mock_process.stdout.readline.side_effect = ["downloading layer 1\n", "downloading layer 2\n", "", "", ""]
    mock_process.return_code = 0
    mock_process.return_code = 0
    # Python mock property trick for returncode
    type(mock_process).returncode = property(lambda self: 0)
    mock_popen.return_value = mock_process

    lines = []
    def callback(l):
        lines.append(l)

    success = pull_model("llama3.1", progress_callback=callback)
    assert success is True
    assert lines == ["downloading layer 1", "downloading layer 2"]
