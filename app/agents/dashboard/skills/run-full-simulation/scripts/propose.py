#!/usr/bin/env python3
"""Proposes carrying out a whole simulation and reporting its metrics."""

import argparse
import os
import sys

# scripts -> <skill> -> skills -> dashboard -> agents -> app -> repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 6)))

from app.agents.dashboard.skill_support import run
from app.core.actions import ActionType

ACTION = ActionType.RUN_FULL_SIMULATION


def build_parser():
    """Returns: argparse.ArgumentParser: The command line this skill accepts."""
    parser = argparse.ArgumentParser(description="Proposes carrying out a whole simulation.")
    parser.add_argument("--steps", type=int, required=True, help="How many steps the run lasts.")
    parser.add_argument("--num-users", type=int, help="How many users to create.")
    parser.add_argument("--num-satellites", type=int, help="Maximum number of satellites.")
    parser.add_argument("--scenario", help="Scenario: hybrid, leo or terrestrial.")
    parser.add_argument("--algorithm", help="Allocation algorithm.")
    return parser


def collect(args):
    """Returns: dict: The step budget, plus only the settings the operator changed.

    Everything omitted keeps what the simulation is configured with, so the
    absent keys are left out rather than sent as None.
    """
    if args.steps < 1:
        raise ValueError(f"steps must be >= 1, got {args.steps}.")

    asked = {
        "num_users": args.num_users,
        "num_satellites": args.num_satellites,
        "scenario": args.scenario,
        "algorithm": args.algorithm,
    }
    settings = {name: value for name, value in asked.items() if value is not None}
    settings["steps"] = args.steps
    return settings


def summarize(arguments):
    """Returns: str: What the gate shows before the runner resolves the rest."""
    changed = {name: value for name, value in arguments.items() if name != "steps"}
    if not changed:
        return f"Run a complete simulation of {arguments['steps']} steps with the current configuration"

    settings = ", ".join(f"{name}={value}" for name, value in sorted(changed.items()))
    return f"Run a complete simulation of {arguments['steps']} steps ({settings})"


if __name__ == "__main__":
    sys.exit(run(ACTION, build_parser(), collect, summarize))
