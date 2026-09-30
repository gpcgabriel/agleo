#!/usr/bin/env python3
"""Proposes adding satellites or ground stations."""

import argparse
import os
import sys

# scripts -> <skill> -> skills -> dashboard -> agents -> app -> repository root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), *[os.pardir] * 6)))

from app.agents.dashboard.skill_support import run
from app.core.actions import ActionType

from app.core.actions import NodeSpec


ACTION = ActionType.ADD_NODES


def build_parser():
    """Returns: argparse.ArgumentParser: The command line this skill accepts."""
    parser = argparse.ArgumentParser(description="Proposes adding satellites or ground stations.")
    parser.add_argument("--node-types", nargs="+", required=True, choices=NodeSpec.NODE_TYPES)
    parser.add_argument("--latitudes", nargs="+", type=float, help="One per node. Optional.")
    parser.add_argument("--longitudes", nargs="+", type=float, help="One per node. Optional.")
    return parser


def collect(args):
    """Returns: dict: The fields the payload needs."""
    if not (args.latitudes and args.longitudes):
        raise ValueError(
            "This skill needs a position. Read the coordinates of a node near the one the operator "
            "described from the context state, and pass --latitudes and --longitudes."
        )
    if len(args.latitudes) != len(args.node_types) or len(args.longitudes) != len(args.node_types):
        raise ValueError(
            f"One latitude and one longitude per node, got {len(args.node_types)} types, "
            f"{len(args.latitudes)} latitudes and {len(args.longitudes)} longitudes."
        )

    # Altitude follows from the node type and capacity is drawn, so neither is
    # asked for: `NodeSpec` fills them and records that it did.
    nodes = [
        {"node_type": kind, "lat": lat, "lon": lon, "defaulted": ["altitude"]}
        for kind, lat, lon in zip(args.node_types, args.latitudes, args.longitudes)
    ]
    return {"nodes": nodes}


if __name__ == "__main__":
    sys.exit(run(ACTION, build_parser(), collect))
