#!/usr/bin/env python3
"""Proposes creating a user at a position."""

import argparse
import os
import sys

# scripts -> <skill> -> skills -> dashboard -> agents -> app -> repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 6)))

from app.agents.dashboard.skill_support import run
from app.core.actions import ActionType


ACTION = ActionType.ADD_USER


def build_parser():
    """Returns: argparse.ArgumentParser: The command line this skill accepts."""
    parser = argparse.ArgumentParser(description="Proposes creating a user at a position.")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--connection-range", type=int, default=1500, help="Signal reach in kilometres.")
    return parser


def collect(args):
    """Returns: dict: The fields the payload needs."""
    return {"lat": args.lat, "lon": args.lon, "connection_range": args.connection_range}


if __name__ == "__main__":
    sys.exit(run(ACTION, build_parser(), collect))
