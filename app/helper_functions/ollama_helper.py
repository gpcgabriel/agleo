import subprocess
import time
from collections.abc import Callable
from typing import Any

import httpx
import ollama
import requests

DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_HOST = "http://localhost:11434"


def is_ollama_running() -> bool:
    """
    Check if the Ollama daemon is reachable at http://localhost:11434/api/tags.
    Returns:
        bool: True if reachable, False otherwise.
    """
    try:
        response = requests.get(f"{DEFAULT_HOST}/api/tags", timeout=2)
        return response.status_code == requests.codes.ok
    except requests.exceptions.RequestException:
        return False


def start_ollama() -> bool:
    """
    Start the Ollama daemon in the background via subprocess.Popen.
    Polls the health-check endpoint for up to 10 seconds.
    Returns:
        bool: True if Ollama became reachable, False otherwise.
    """
    if is_ollama_running():
        return True

    try:
        # Starting Ollama serve in the background, redirecting stdout and stderr
        # so they do not pollute the logs, and finding `ollama` through PATH as the
        # operator's shell does: resolving it to an absolute path first would only
        # trade this S607 for an S603, because starting a daemon takes a subprocess.
        subprocess.Popen(
            ["ollama", "serve"],  # noqa: S607
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Ensure it runs independently
        )
    except OSError:
        return False

    # Polling for up to 10 seconds (20 retries * 0.5 seconds).
    for _ in range(20):
        time.sleep(0.5)
        if is_ollama_running():
            return True

    return False


def list_local_models() -> list[str]:
    """
    Query GET /api/tags to list downloaded model names.
    Returns:
        List[str]: A list of downloaded model names.
    """
    try:
        response = requests.get(f"{DEFAULT_HOST}/api/tags", timeout=3)
        models_list: list[dict[str, Any]] = (
            response.json().get("models", []) if response.status_code == requests.codes.ok else []
        )
    except requests.exceptions.RequestException:
        return []

    # Extracting the names, tolerating variations in the response structure.
    return [model["name"] for model in models_list if "name" in model]


def describe_pull_progress(update: ollama.ProgressResponse) -> str:
    """Returns one line saying what a download is doing, with its percentage once the size is known."""
    status = update.status or ""
    if update.total and update.completed is not None:
        return f"{status} {update.completed / update.total:.0%}"
    return status


def pull_model(model_name: str, progress_callback: Callable[[str], None] | None = None) -> bool:
    """Downloads a model through the Ollama API, reporting each step of the download.

    Args:
        model_name (str): The model to download, with or without its tag.
        progress_callback (Callable): Receives one line per progress update, when given.

    Returns:
        bool: True once the download has finished, False when Ollama refused it or
        could not be reached.
    """
    try:
        for update in ollama.Client(host=DEFAULT_HOST).pull(model_name, stream=True):
            line = describe_pull_progress(update)
            if progress_callback and line:
                progress_callback(line)
    except (ollama.ResponseError, ConnectionError, httpx.HTTPError):
        return False

    return True


def model_is_available(model_name: str, local_models: list[str] | None = None) -> bool:
    """Tells whether a model is available locally, tolerating the tag.

    A name may or may not carry its tag: "llama3.1" and "llama3.1:8b" refer to
    the same local model, and either form can reach here.

    Args:
        model_name (str): Name of the model being looked for.
        local_models (list): Local models; queried when not supplied.

    Returns:
        bool: True if some local model matches.
    """
    if local_models is None:
        local_models = list_local_models()

    return any(
        name == model_name or name.startswith(model_name + ":") or model_name.startswith(name + ":")
        for name in local_models
    )
