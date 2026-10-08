"""Captures satellite traces from the N2YO API into a traces file.

The file holds one list per capture, of the satellites the API reported above the reference
point: the format of `datasets/satellites_brazil.json`, which `main.py --satellites` and the
dashboard read. The key comes from the environment:

    uv run --env-file .env python -m dataset_generator --output traces.json --steps 840
"""

import argparse
import json
import os
import sys

from dataset_generator.create_components import (
    CAPTURE_INTERVAL_SECONDS,
    MAX_SEARCH_RADIUS,
    Sighting,
    stream_steps_from_api,
)

DEFAULT_STEPS = 10


def parse_arguments(arguments: list[str]) -> argparse.Namespace:
    """Reads the capture's settings from the command line.

    Args:
        arguments (list): The command-line arguments, without the program name.

    Returns:
        argparse.Namespace: `output`, `steps`, `interval` and `radius`.
    """
    parser = argparse.ArgumentParser(
        prog="python -m dataset_generator",
        description="Captures satellite traces from the N2YO API into a traces file.",
    )
    parser.add_argument("--output", required=True, help="Traces file to write; it must not exist yet.")
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS, help="Captures to take (default: %(default)s).")
    parser.add_argument(
        "--interval",
        type=int,
        default=CAPTURE_INTERVAL_SECONDS,
        help="Seconds between two captures (default: %(default)s; the API allows 100 requests an hour).",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=MAX_SEARCH_RADIUS,
        help="Search radius in degrees from the zenith, 0 to 90 (default: %(default)s, the whole sky).",
    )
    options = parser.parse_args(arguments)

    # Guarding the existing file: a capture that fails before its first answer would replace it.
    if os.path.exists(options.output):
        parser.error(f"{options.output} already exists; choose another path.")
    if options.steps < 1:
        parser.error(f"Invalid --steps: {options.steps!r}. Expected at least 1.")
    if options.interval < 0:
        parser.error(f"Invalid --interval: {options.interval!r}. Expected 0 seconds or more.")
    return options


def write_traces(steps: list[list[Sighting]], output: str) -> None:
    """Writes captures as a traces file."""
    with open(output, "w", encoding="UTF-8") as file:
        json.dump(steps, file)


def main(arguments: list[str]) -> None:
    """Takes the capture the command line asks for and writes it.

    What was captured before a failure or an interruption is written before the error
    propagates, so a long capture is never lost to its last request.

    Args:
        arguments (list): The command-line arguments, without the program name.
    """
    options = parse_arguments(arguments)
    steps = []

    try:
        for step in stream_steps_from_api(options.steps, options.interval, options.radius):
            steps.append(step)
            print(f"Capture {len(steps)}/{options.steps}: {len(step)} satellites", flush=True)
    finally:
        if steps:
            write_traces(steps, options.output)
            print(f"Wrote {len(steps)} of {options.steps} captures to {options.output}", flush=True)
        else:
            print(f"Nothing captured; {options.output} was not written", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
