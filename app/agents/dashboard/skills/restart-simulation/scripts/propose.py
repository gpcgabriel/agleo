#!/usr/bin/env python3
"""Proposes restarting the simulation at step zero."""

import argparse
import os
import sys

# scripts -> <skill> -> skills -> dashboard -> agents -> app -> repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 6)))

from app.agents.dashboard.skill_support import run
from app.core.actions import ActionType


ACTION = ActionType.RESTART_SIMULATION


def build_parser():
    """Returns: argparse.ArgumentParser: The command line this skill accepts."""
    parser = argparse.ArgumentParser(description="Proposes restarting the simulation at step zero.")
    parser.add_argument("--num-users", type=int, help="How many users to create.")
    parser.add_argument("--num-satellites", type=int, help="Maximum number of satellites.")
    parser.add_argument("--scenario", help="Scenario: hybrid, leo or terrestrial.")
    parser.add_argument("--algorithm", help="Allocation algorithm.")
    parser.add_argument("--gml-path", help="Terrestrial topology file.")
    parser.add_argument("--satellites-path", help="Satellite traces file.")
    return parser


def collect(args):
    """Returns: dict: Only the settings the operator asked to change.

    Everything omitted keeps what the simulation is running with, so the
    absent keys are left out rather than sent as None.
    """
    asked = {
        "num_users": args.num_users,
        "num_satellites": args.num_satellites,
        "scenario": args.scenario,
        "algorithm": args.algorithm,
        "gml_path": args.gml_path,
        "satellites_path": args.satellites_path,
    }
    return {name: value for name, value in asked.items() if value is not None}


def summarize(arguments):
    """Returns: str: What the gate shows before the runner resolves the rest."""
    if not arguments:
        return "Reset simulation to Step 0 with the current configuration"

    changes = ", ".join(f"{name}={value}" for name, value in sorted(arguments.items()))
    return f"Reset simulation to Step 0 ({changes})"


if __name__ == "__main__":
    sys.exit(run(ACTION, build_parser(), collect, summarize))
