"""Measures the dashboard agent's two capability models against each other.

Phase 6 asks whether progressive disclosure steers a small local model better
than function calling. The prompt sizes were calculated without running
anything; this runs it. Both modes go through the same `run_agent`, so what is
compared is the capability model and not two different pipelines.

    ~/.pyenv/versions/3.12.9/bin/python benchmark_modes.py --repetitions 3

Writes one JSON line per run to `logs/mode_benchmark.jsonl` and prints a
summary table.
"""

import argparse
import os
import sys
import time
from json import dumps
from statistics import median

from app.agents.dashboard.runner import MODE_SKILLS, MODE_TOOLS, SKILLS_DIRECTORY, run_agent
from app.core.actions import ActionType
from app.core.config import SimulationConfig
from app.core.session import create_session
from app.core.snapshot import find_default_node_position
from app.core.router import QUICK_COMMAND_CONTEXT, build_agent_context
from app.helper_functions.ollama_helper import DEFAULT_MODEL, is_ollama_running, model_is_available

LOG_PATH = os.path.join("logs", "mode_benchmark.jsonl")

# What gets compared: six tool schemas in the system prompt against progressive
# disclosure, where the model sees a short skill description and opens the rest
# only when it judges the skill relevant.
ARMS = {
    "Tools": (MODE_TOOLS, None),
    "Skills": (MODE_SKILLS, SKILLS_DIRECTORY),
}


class Command:
    """One operator command and what a correct answer to it looks like."""

    def __init__(self, label, text, expected_action, check=None):
        """Args:
        label (str): Short name for the summary table.
        text (str): What the operator types.
        expected_action (str): The ActionType that should be proposed, or
            None when the command is informational and nothing should be.
        check (callable): Takes the proposal's payload and returns True if
            the parameters are right. None means any payload passes.
        """
        self.label = label
        self.text = text
        self.expected_action = expected_action
        self.check = check


def steps_are(expected):
    return lambda payload: getattr(payload, "steps", None) == expected


def one_satellite(payload):
    return getattr(payload, "nodes", None) is not None and [node.node_type for node in payload.nodes] == ["Satellite"]


def user_is_placed(payload):
    return getattr(payload, "lat", None) is not None and getattr(payload, "lon", None) is not None


def unit_has(cpu, memory):
    return lambda payload: getattr(payload, "cpu", None) == cpu and getattr(payload, "memory", None) == memory


def app_for_user(user_id):
    return lambda payload: getattr(payload, "user_id", None) == user_id


COMMANDS = [
    Command("step/slash", "/step 3", ActionType.RUN_SIMULATION, steps_are(3)),
    Command("step/prose", "Advance the simulation by 3 steps", ActionType.RUN_SIMULATION, steps_are(3)),
    Command(
        "add satellite",
        "Add one satellite at latitude -7.2 and longitude -35.8",
        ActionType.ADD_NODES,
        one_satellite,
    ),
    Command(
        "add user",
        "Create a user at latitude -23.5 and longitude -46.6",
        ActionType.ADD_USER,
        user_is_placed,
    ),
    Command(
        "add process unit",
        "Add a process unit with 40 CPU and 40 memory to satellite 3",
        ActionType.ADD_PROCESS_UNIT,
        unit_has(40, 40),
    ),
    Command(
        "add application",
        "Give user 2 an application that needs 20 CPU and 30 memory",
        ActionType.ADD_APP_TO_USER,
        app_for_user(2),
    ),
    Command("count question", "How many ground stations are in the network?", None),
    Command("state question", "Which satellites are currently active?", None),
]


def resolve_context(command, snapshot, size):
    """Builds the context one run is given.

    Args:
        command (Command): The command being sent.
        snapshot (dict): State the full context is built from.
        size (str): "router" for what the application sends, or "short" and
            "full" to hold the context fixed across commands.

    Returns:
        str: The context to inject.
    """
    if size == "short":
        return QUICK_COMMAND_CONTEXT

    if size == "full":
        return build_agent_context("describe the network", snapshot)

    return build_agent_context(command.text, snapshot)


def build_context():
    """Builds the session every command is measured against.

    Returns:
        tuple: (snapshot, SimulationConfig, default position).
    """
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=20,
        num_satellites=15,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    session = create_session(config)
    snapshot = session.get_current_snapshot()

    return snapshot, config, find_default_node_position(snapshot)


def score(command, result):
    """Grades one run against what the command asked for.

    Returns:
        dict: What the agent got right, and what it cost.
    """
    proposal = result.get_primary_proposal()

    if command.expected_action is None:
        return {
            "proposed": proposal is not None,
            "right_action": proposal is None,
            "right_parameters": proposal is None,
        }

    if proposal is None:
        return {"proposed": False, "right_action": False, "right_parameters": False}

    right_action = proposal.action_type == command.expected_action
    right_parameters = right_action and (command.check is None or bool(command.check(proposal.payload)))

    return {"proposed": True, "right_action": right_action, "right_parameters": right_parameters}


def run_once(command, arm, model_name, snapshot, config, position, context_size="router"):
    """Runs one command in one arm and records the result.

    Args:
        command (Command): What to send and what a correct answer looks like.
        arm (str): A key of `ARMS`.
        model_name (str): Model identifier in Ollama.
        snapshot (dict): State the context is built from.
        config (SimulationConfig): Active configuration.
        position (tuple): Default position for an unplaced node.
        context_size (str): Which context to send; see `resolve_context`.

    Returns:
        dict: One benchmark record.
    """
    mode, skills_directory = ARMS[arm]

    started = time.monotonic()
    try:
        context = resolve_context(command, snapshot, context_size)
        result = run_agent(
            command.text,
            model_name,
            mode,
            context,
            current_config=config,
            default_position=position,
            skills_directory=skills_directory,
        )
        failure = None
    except Exception as error:
        elapsed = time.monotonic() - started
        return {
            "arm": arm,
            "command": command.label,
            "context_size": context_size,
            "elapsed_seconds": round(elapsed, 2),
            "proposed": False,
            "right_action": False,
            "right_parameters": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": f"{type(error).__name__}: {error}",
        }

    elapsed = time.monotonic() - started
    record = {
        "arm": arm,
        "command": command.label,
        "context_size": context_size,
        "elapsed_seconds": round(elapsed, 2),
        "input_tokens": result.usage.get("input_tokens", 0),
        "output_tokens": result.usage.get("output_tokens", 0),
        "error": failure,
    }
    record.update(score(command, result))
    return record


def summarize(records):
    """Aggregates the records into one row per mode.

    Returns:
        list: One row per mode.
    """
    rows = []
    for arm in ARMS:
        mine = [record for record in records if record["arm"] == arm]
        if not mine:
            continue

        actionable = [r for r in mine if r["command"] not in ("count question", "state question")]
        informational = [r for r in mine if r["command"] in ("count question", "state question")]

        rows.append(
            {
                "arm": arm,
                "runs": len(mine),
                "median_seconds": round(median(r["elapsed_seconds"] for r in mine), 1),
                "median_input_tokens": int(median(r["input_tokens"] for r in mine)),
                "median_output_tokens": int(median(r["output_tokens"] for r in mine)),
                "proposed_when_asked": f"{sum(r['proposed'] for r in actionable)}/{len(actionable)}",
                "right_action": f"{sum(r['right_action'] for r in actionable)}/{len(actionable)}",
                "right_parameters": f"{sum(r['right_parameters'] for r in actionable)}/{len(actionable)}",
                "stayed_quiet_when_asked_a_question": f"{sum(not r['proposed'] for r in informational)}/{len(informational)}",
                "errors": sum(1 for r in mine if r["error"]),
            }
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description="Compare the dashboard agent's Tools and Skills modes.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model identifier in Ollama.")
    parser.add_argument("--repetitions", type=int, default=3, help="Runs per command per arm.")
    parser.add_argument("--arms", nargs="+", default=list(ARMS), choices=list(ARMS), help="Which arms to run.")
    parser.add_argument("--only", nargs="+", help="Run only these command labels.")
    parser.add_argument(
        "--contexts",
        nargs="+",
        default=["router"],
        choices=["router", "short", "full"],
        help="Which context to send. 'router' is what the application sends; the other two hold it "
        "fixed across commands so context load can be separated from the command itself.",
    )
    arguments = parser.parse_args()

    if not is_ollama_running():
        print("Ollama is not running.")
        return 1
    if not model_is_available(arguments.model):
        print(f"Model {arguments.model!r} is not available locally.")
        return 1

    snapshot, config, position = build_context()
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

    commands = [c for c in COMMANDS if not arguments.only or c.label in arguments.only]
    records = []
    total = len(commands) * len(arguments.arms) * len(arguments.contexts) * arguments.repetitions
    done = 0

    with open(LOG_PATH, "a", encoding="utf-8") as log_file:
        for repetition in range(arguments.repetitions):
            for command in commands:
                for context_size in arguments.contexts:
                    for arm in arguments.arms:
                        record = run_once(command, arm, arguments.model, snapshot, config, position, context_size)
                        record["repetition"] = repetition
                        record["model"] = arguments.model
                        records.append(record)
                        log_file.write(dumps(record) + "\n")
                        log_file.flush()

                        done += 1
                        print(
                            f"[{done}/{total}] {arm:16s} {context_size:6s} {command.label:18s} "
                            f"{record['elapsed_seconds']:6.1f}s  action={record['right_action']} "
                            f"params={record['right_parameters']}"
                            + (f"  ERROR {record['error']}" if record["error"] else ""),
                            flush=True,
                        )

    print("\n=== Summary ===")
    for row in summarize(records):
        print(dumps(row, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
