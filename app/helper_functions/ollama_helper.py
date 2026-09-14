import subprocess
import time
import requests
from typing import List, Callable, Optional

DEFAULT_MODEL = "llama3.1"


def is_ollama_running() -> bool:
    """
    Check if the Ollama daemon is reachable at http://localhost:11434/api/tags.
    Returns:
        bool: True if reachable, False otherwise.
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        return response.status_code == 200
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
        # Start Ollama serve in the background. Redirect stdout/stderr to avoid polluting logs.
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Ensure it runs independently
        )
    except Exception:
        return False

    # Poll for up to 10 seconds (20 retries * 0.5 seconds)
    for _ in range(20):
        time.sleep(0.5)
        if is_ollama_running():
            return True

    return False


def list_local_models() -> List[str]:
    """
    Query GET /api/tags to list downloaded model names.
    Returns:
        List[str]: A list of downloaded model names.
    """
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        if response.status_code == 200:
            data = response.json()
            models_list = data.get("models", [])
            # Extract names, handling potential structure variations
            return [model["name"] for model in models_list if "name" in model]
    except Exception:
        pass
    return []


def pull_model(model_name: str, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
    """
    Execute 'ollama pull <model_name>' via subprocess, streaming stdout.
    Calls progress_callback with each line of output if provided.
    Returns:
        bool: True if download succeeded, False otherwise.
    """
    try:
        process = subprocess.Popen(
            ["ollama", "pull", model_name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
        )

        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                clean_line = line.strip()
                if progress_callback and clean_line:
                    progress_callback(clean_line)

        return process.returncode == 0
    except Exception:
        return False


def model_is_available(model_name: str, local_models=None) -> bool:
    """Tells whether a model is available locally, tolerating the tag.

    The sidebar selector works with full names ("llama3.1:8b"), while
    DEFAULT_MODEL is the untagged name ("llama3.1"). This comparison accepts
    either form.

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
