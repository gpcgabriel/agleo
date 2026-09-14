"""Integration tests for the agent commands.

They need a running Ollama with the default model pulled; otherwise they are
skipped. They exercise exactly the code path the application uses in
production, with no duplicated prompts and no Streamlit mock.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.runner import MODE_TOOLS, run_agent
from app.core.actions import ActionType
from app.core.config import SimulationConfig
from app.helper_functions.ollama_helper import DEFAULT_MODEL, is_ollama_running, list_local_models

QUICK_COMMAND_CONTEXT = (
    "Quick Command Mode (Slash Command). "
    "Execute the corresponding action immediately by calling the appropriate tool."
)


def make_config():
    return SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=20,
        num_satellites=15,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )


def resolve_model():
    """Resolves the default model to a tag present in the local Ollama.

    `DEFAULT_MODEL` is the untagged name ("llama3.1"), while the Ollama API
    needs the full tag ("llama3.1:8b").

    Returns:
        str or None: A usable model name, or None if there is none.
    """
    if not is_ollama_running():
        return None

    for name in list_local_models():
        if name == DEFAULT_MODEL or name.startswith(DEFAULT_MODEL + ":") or DEFAULT_MODEL.startswith(name + ":"):
            return name
    return None


def test_step_command_proposes_running_the_simulation():
    model = resolve_model()
    if model is None:
        print("  SKIP  test_step_command_proposes_running_the_simulation (Ollama or model unavailable)")
        return

    result = run_agent("/step 5", model, MODE_TOOLS, QUICK_COMMAND_CONTEXT, make_config())
    action = result.get_primary_proposal()

    assert action is not None, "the agent proposed no action"
    assert action.action_type == ActionType.RUN_SIMULATION
    assert action.payload.steps == 5


def test_restart_command_proposes_restarting_with_current_config():
    model = resolve_model()
    if model is None:
        print("  SKIP  test_restart_command_proposes_restarting_with_current_config (Ollama or model unavailable)")
        return

    result = run_agent("/restart", model, MODE_TOOLS, QUICK_COMMAND_CONTEXT, make_config())
    action = result.get_primary_proposal()

    assert action is not None, "the agent proposed no action"
    assert action.action_type == ActionType.RESTART_SIMULATION
    assert action.payload.config.scenario == "hybrid"


def test_review_command_answers_without_proposing_anything():
    model = resolve_model()
    if model is None:
        print("  SKIP  test_review_command_answers_without_proposing_anything (Ollama or model unavailable)")
        return

    context = (
        "You have access to the current detailed simulation state below:\n\n"
        "[SIMULATION STATE] User 1 is disconnected. Ground Station 28 has 0 servers.\n\n"
        "Use this data to answer."
    )
    result = run_agent("/review", model, MODE_TOOLS, context, make_config())

    assert not result.has_proposals(), f"/review should propose nothing, proposed {result.proposals}"
    assert "disconnected" in result.text.lower() or "user 1" in result.text.lower()


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
