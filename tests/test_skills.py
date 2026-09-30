"""Tests for the dashboard agent's skills.

The two modes are the capability models being compared: six tool schemas in
the system prompt, against progressive disclosure where the model sees a short
description and opens the rest only when it judges the skill relevant. Neither
mode may carry the other's mechanism, or the comparison measures nothing.

A skill script runs as a subprocess and cannot reach the proposal buffer, so
these also cover the path that reads its output back.
"""

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agno.skills import LocalSkills

from app.agents.dashboard.prompts import dashboard_agent_description, dashboard_agent_instructions
from app.agents.dashboard.runner import (
    MODE_SKILLS,
    MODE_TOOLS,
    SKILL_SCRIPT_TOOL,
    SKILLS_DIRECTORY,
    build_agent,
    collect_script_proposals,
)
from app.agents.dashboard.tools import ProposalBuffer
from app.core.actions import ActionType, build_payload
from app.core.config import SimulationConfig

MODEL_FOR_ASSEMBLY = "llama3.2:3b"
EXPECTED_SKILLS = {
    "run-simulation": ["--steps", "5"],
    "add-user": ["--lat", "-23.5", "--lon", "-46.6"],
    "add-nodes": ["--node-types", "Satellite", "--latitudes", "-7.2", "--longitudes", "-35.8"],
    "add-process-unit": ["--target-type", "Satellite", "--target-id", "3", "--cpu", "40", "--memory", "40"],
    "add-app-to-user": ["--user-id", "2", "--cpu", "20", "--memory", "30"],
    "restart-simulation": ["--num-users", "40", "--scenario", "leo"],
}

# Restarting is resolved against the configuration in use, which the subprocess
# cannot see, so its script prints arguments the runner completes.
DEFERRED_SKILLS = {"restart-simulation"}


def script_of(skill_name):
    return os.path.join(SKILLS_DIRECTORY, skill_name, "scripts", "propose.py")


class FakeExecution:
    """Stands in for one agno tool execution."""

    def __init__(self, tool_name, result):
        self.tool_name = tool_name
        self.result = result


class FakeResponse:
    """Stands in for what `agent.run` returns."""

    def __init__(self, tools):
        self.tools = tools


def load_skills():
    return LocalSkills(SKILLS_DIRECTORY).load()


def test_the_skills_directory_travels_with_the_package():
    """Streamlit is launched from wherever the operator is, not from the repo root."""
    assert os.path.isabs(SKILLS_DIRECTORY)
    assert os.path.isdir(SKILLS_DIRECTORY)


def test_every_skill_on_disk_is_valid():
    """`LocalSkills` validates on load, so an invalid skill raises here."""
    skills = load_skills()

    assert skills, "no skills found"


def test_each_skill_declares_a_name_and_a_description():
    for skill in load_skills():
        assert skill.name, f"{skill.source_path} has no name"
        assert skill.description, f"{skill.name} has no description"
        assert skill.instructions.strip(), f"{skill.name} has no instructions"


def test_a_description_says_when_to_use_the_skill():
    """The description is all the model sees before deciding to open a skill."""
    for skill in load_skills():
        assert "use when" in skill.description.lower(), f"{skill.name} does not say when it applies"


def test_tools_mode_builds_with_the_proposal_tools():
    agent = build_agent(MODEL_FOR_ASSEMBLY, MODE_TOOLS, ProposalBuffer())

    assert len(agent.tools) == len(ProposalBuffer().get_tools())


def test_skills_mode_builds_instead_of_raising():
    agent = build_agent(MODEL_FOR_ASSEMBLY, MODE_SKILLS, ProposalBuffer())

    assert agent is not None


def test_skills_mode_does_not_get_the_proposal_tools():
    """The two modes are the comparison: tool schemas against progressive disclosure.

    Handing this mode the tools as well would leave nothing to compare.
    """
    agent = build_agent(MODEL_FOR_ASSEMBLY, MODE_SKILLS, ProposalBuffer())

    assert not (agent.tools or [])


def test_a_skill_script_proposal_reaches_the_buffer():
    """A script runs as a subprocess, so its output has to be read back."""
    printed = json.dumps(
        {
            "stdout": json.dumps(
                {
                    "proposal": {
                        "action_type": "add_user",
                        "arguments": {"lat": -23.5, "lon": -46.6, "connection_range": 1500},
                        "description": "Create user at (-23.5000, -46.6000) with range of 1500km",
                    }
                }
            )
        }
    )
    buffer = ProposalBuffer()

    recorded = collect_script_proposals(FakeResponse([FakeExecution(SKILL_SCRIPT_TOOL, printed)]), buffer)

    assert recorded == 1
    assert buffer.get_proposals()[0].action_type == "add_user"


def test_a_script_that_failed_proposes_nothing():
    printed = json.dumps({"stdout": json.dumps({"error": "steps must be >= 1, got 0."})})
    buffer = ProposalBuffer()

    recorded = collect_script_proposals(FakeResponse([FakeExecution(SKILL_SCRIPT_TOOL, printed)]), buffer)

    assert recorded == 0
    assert buffer.get_proposals() == []


def test_a_proposal_with_invalid_arguments_is_refused_here_too():
    """The script validates, but the runner must not trust it to have done so."""
    printed = json.dumps(
        {"stdout": json.dumps({"proposal": {"action_type": "run_simulation", "arguments": {"steps": 0}}})}
    )
    buffer = ProposalBuffer()

    recorded = collect_script_proposals(FakeResponse([FakeExecution(SKILL_SCRIPT_TOOL, printed)]), buffer)

    assert recorded == 0


def test_other_tool_results_are_ignored():
    buffer = ProposalBuffer()

    recorded = collect_script_proposals(FakeResponse([FakeExecution("get_skill_instructions", "{}")]), buffer)

    assert recorded == 0


def test_there_is_one_skill_per_action():
    """Progressive disclosure is the point: a single skill would load everything.

    With one skill per action, an operator who only instantiates applications
    never pays for the instructions on adding satellites.
    """
    assert {skill.name for skill in load_skills()} == set(EXPECTED_SKILLS)


def test_there_is_one_skill_per_tool():
    """The comparison only measures the capability model if both modes can do
    the same things. Restarting was the one action Tools had and Skills did
    not, which made every run of that command a Tools win by construction."""
    assert len(load_skills()) == len(ProposalBuffer().get_tools())


def test_each_skill_proposes_the_action_it_is_named_for():
    for skill_name, arguments in EXPECTED_SKILLS.items():
        result = subprocess.run(
            [sys.executable, script_of(skill_name)] + arguments, capture_output=True, text=True, timeout=60
        )
        printed = json.loads(result.stdout)

        assert "proposal" in printed, f"{skill_name}: {printed}"
        assert printed["proposal"]["action_type"] == skill_name.replace("-", "_")


def test_a_node_gets_an_altitude_without_being_asked_for_one():
    """Altitude follows from the node type; asking the operator for it is noise."""
    result = subprocess.run(
        [sys.executable, script_of("add-nodes")] + EXPECTED_SKILLS["add-nodes"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    proposal = json.loads(result.stdout)["proposal"]

    assert "550km" in proposal["description"]
    assert "altitude" in proposal["chosen_automatically"]


def test_the_description_never_carries_the_note_the_model_reads():
    """The agent once passed "[chosen automatically: altitude]" back as a parameter."""
    result = subprocess.run(
        [sys.executable, script_of("add-nodes")] + EXPECTED_SKILLS["add-nodes"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    proposal = json.loads(result.stdout)["proposal"]

    assert "chosen" not in proposal["description"].lower()
    assert "[" not in proposal["description"]


def test_a_skill_script_rejects_what_the_payload_rejects():
    result = subprocess.run(
        [sys.executable, script_of("run-simulation"), "--steps", "0"], capture_output=True, text=True, timeout=60
    )

    assert json.loads(result.stdout)["error"].startswith("steps must be >= 1")


def test_restarting_proposes_only_the_settings_the_operator_named():
    """Anything left out has to keep what the simulation is running with, so an
    absent setting must not travel as None and overwrite it."""
    result = subprocess.run(
        [sys.executable, script_of("restart-simulation"), "--num-users", "40"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    arguments = json.loads(result.stdout)["proposal"]["arguments"]

    assert arguments == {"num_users": 40}


def test_a_plain_restart_carries_no_settings_at_all():
    result = subprocess.run(
        [sys.executable, script_of("restart-simulation")], capture_output=True, text=True, timeout=60
    )
    proposal = json.loads(result.stdout)["proposal"]

    assert proposal["arguments"] == {}
    assert "current configuration" in proposal["description"]


def test_a_restart_is_refused_without_the_configuration_in_use():
    """`RestartSimulationPayload` takes a resolved config; the runner supplies
    it, and building one without it must fail rather than invent defaults."""
    try:
        build_payload(ActionType.RESTART_SIMULATION, {"num_users": 40})
    except ValueError as error:
        assert "configuration currently loaded" in str(error)
    else:
        raise AssertionError("a restart was built with no configuration")


def test_a_restart_reaches_the_buffer_once_the_runner_supplies_the_configuration():
    config = SimulationConfig(
        gml_path="datasets/rnp.gml",
        satellites_path="datasets/satellites_brazil.json",
        num_users=20,
        num_satellites=15,
        scenario="hybrid",
        algorithm="best_fit_allocation",
    )
    printed = json.dumps(
        {"stdout": json.dumps({"proposal": {"action_type": "restart_simulation", "arguments": {"num_users": 40}}})}
    )
    buffer = ProposalBuffer(current_config=config)

    recorded = collect_script_proposals(FakeResponse([FakeExecution(SKILL_SCRIPT_TOOL, printed)]), buffer)

    assert recorded == 1
    assert buffer.get_proposals()[0].payload.config.num_users == 40
    assert buffer.get_proposals()[0].payload.config.scenario == "hybrid"


def test_every_skill_script_runs_by_itself():
    """agno executes a script directly through its shebang, so a missing `#!`
    or a missing executable bit comes back as `Exec format error` and the skill
    can propose nothing. Four of six had no executable bit and none had a
    shebang, which is what made Skills mode look incapable."""
    for skill_name in EXPECTED_SKILLS:
        path = script_of(skill_name)

        assert os.access(path, os.X_OK), f"{skill_name}/scripts/propose.py is not executable"
        with open(path, encoding="utf-8") as script:
            assert script.readline().startswith("#!"), f"{skill_name}/scripts/propose.py has no shebang"


def test_no_skill_carries_more_than_one_action():
    """Two actions in one skill would be two reasons to load it."""
    for skill_name in EXPECTED_SKILLS:
        source = open(script_of(skill_name), encoding="utf-8").read()

        assert source.count("ACTION = ActionType.") == 1, f"{skill_name} proposes more than one action"


def test_the_shared_prompt_names_neither_mode_s_mechanism():
    """Both modes read the same instructions. Naming a tool in them hands one
    mode's mechanism to the other: measured 30 September 2026, the model in
    Skills mode opened no skill and wrote `propose_add_node` out as text."""
    text = dashboard_agent_description() + " " + " ".join(dashboard_agent_instructions())

    for word in ("propose_", "tool", "skill"):
        assert word not in text.lower(), f"the shared prompt names a mechanism: {word!r}"


def test_an_unknown_mode_is_refused_by_name():
    try:
        build_agent(MODEL_FOR_ASSEMBLY, "Telepathy", ProposalBuffer())
    except ValueError as error:
        assert "Telepathy" in str(error)
    else:
        raise AssertionError("an unknown mode was accepted")


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
