#!/usr/bin/env python3
"""Proposes advancing the simulation clock."""

import argparse
import os
import sys

# scripts -> <skill> -> skills -> dashboard -> agents -> app -> repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 6)))

from app.agents.dashboard.skill_support import run
from app.core.actions import ActionType


ACTION = ActionType.RUN_SIMULATION


def build_parser():
    """Returns: argparse.ArgumentParser: The command line this skill accepts."""
    parser = argparse.ArgumentParser(description="Proposes advancing the simulation clock.")
    parser.add_argument("--steps", type=int, required=True, help="How many ticks to advance.")
    return parser


def collect(args):
    """Returns: dict: The fields the payload needs."""
    return {"steps": args.steps}


if __name__ == "__main__":
    sys.exit(run(ACTION, build_parser(), collect))
