#!/usr/bin/env python3
"""Proposes giving an application to a user."""

import argparse
import os
import sys

# scripts -> <skill> -> skills -> dashboard -> agents -> app -> repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 6)))

from app.agents.dashboard.skill_support import run
from app.core.actions import ActionType


ACTION = ActionType.ADD_APP_TO_USER


def build_parser():
    """Returns: argparse.ArgumentParser: The command line this skill accepts."""
    parser = argparse.ArgumentParser(description="Proposes giving an application to a user.")
    parser.add_argument("--user-id", type=int, required=True, help="Id of the user that will own it.")
    parser.add_argument("--cpu", type=int, required=True, help="CPU the application demands.")
    parser.add_argument("--memory", type=int, required=True, help="Memory the application demands.")
    return parser


def collect(args):
    """Returns: dict: The fields the payload needs."""
    return {"user_id": args.user_id, "cpu": args.cpu, "memory": args.memory}


if __name__ == "__main__":
    sys.exit(run(ACTION, build_parser(), collect))
