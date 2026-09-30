#!/usr/bin/env python3
"""Proposes attaching a process unit to a node."""

import argparse
import os
import sys

# scripts -> <skill> -> skills -> dashboard -> agents -> app -> repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 6)))

from app.agents.dashboard.skill_support import run
from app.core.actions import ActionType

from app.core.actions import NodeSpec


ACTION = ActionType.ADD_PROCESS_UNIT


def build_parser():
    """Returns: argparse.ArgumentParser: The command line this skill accepts."""
    parser = argparse.ArgumentParser(description="Proposes attaching a process unit to a node.")
    parser.add_argument("--target-type", choices=NodeSpec.NODE_TYPES, required=True)
    parser.add_argument("--target-id", type=int, required=True, help="Id of the node that will host the unit.")
    parser.add_argument("--cpu", type=int, required=True)
    parser.add_argument("--memory", type=int, required=True)
    return parser


def collect(args):
    """Returns: dict: The fields the payload needs."""
    return {
        "target_type": args.target_type,
        "target_id": args.target_id,
        "cpu": args.cpu,
        "memory": args.memory,
    }


if __name__ == "__main__":
    sys.exit(run(ACTION, build_parser(), collect))
