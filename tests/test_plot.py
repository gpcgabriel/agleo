"""Tests for the plots of the CLI's metrics.

Every figure is computed by one function and drawn by another, so these write a few rows of
metrics by hand, in the layout `main.py` writes, and check what each figure would show. The
drawing itself is only checked for producing its file.
"""

import json
import os
import sys
import tempfile
from functools import partial
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plot import (
    Row,
    RunLogs,
    average_runs,
    compare_algorithms_averaged,
    migration_series,
    plot_avg_resource_consumption,
    plot_avg_topology,
    plot_delay_by_groundstation,
    plot_groundstation_links_by_id,
    plot_migrations,
    plot_provisioned_in_topology,
    provisioned_series,
    resource_series,
    station_delay_series,
    station_link_series,
    user_access_series,
)

INFINITE = float("inf")


def access(requested: bool, provisioned: bool, delay: float = 1.0) -> dict[str, Any]:
    """Returns: dict: One application access as `User.collect_metrics` records it."""
    return {
        "Request Provisioning": requested,
        "Is Provisioned": provisioned,
        "Provisioning": provisioned,
        "Delay": delay,
    }


def user(
    user_id: int, application_access: dict[str, Any], access_points: tuple[str, ...] | list[str] = ()
) -> dict[str, Any]:
    """Returns: dict: One user's metrics, with a single application."""
    return {"ID": user_id, "Access to Applications": [application_access], "Network Access Points": list(access_points)}


def write_run(directory: str, filename: str, rows: list[Row]) -> None:
    """Writes rows as the JSON Lines file a run leaves behind."""
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, filename), "w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row) + "\n")


def application_rows(hosted_per_step: list[int]) -> list[Row]:
    """Returns: list: Application rows where the given number of applications is hosted at each step."""
    rows = []
    for step, hosted in enumerate(hosted_per_step):
        metrics = [
            {
                "ID": index,
                "Process Unit": "ProcessUnit_1",
                "Available": True,
                "CPU Demand": 10,
                "Memory Demand": 20,
                "Last Migration": {"origin": "None", "target": "ProcessUnit_1"},
            }
            for index in range(hosted)
        ]
        rows.append({"Step": step, "metrics": metrics})
    return rows


def user_rows(provisioned_per_step: list[int]) -> list[Row]:
    """Returns: list: User rows where the first users are served, all on ground station 1."""
    return [
        {
            "Step": step,
            "metrics": [
                user(index, access(True, index < provisioned), access_points=["GroundStation_1"]) for index in range(3)
            ],
        }
        for step, provisioned in enumerate(provisioned_per_step)
    ]


# -- What each figure shows ----------------------------------------------------


def test_a_user_counts_from_its_second_step():
    """There is nothing to compare a user's first step with, so it is not counted."""
    rows = [
        {"Step": 0, "metrics": [user(1, access(True, True, delay=5.0))]},
        {"Step": 1, "metrics": [user(1, access(True, True, delay=2.0))]},
    ]

    steps, provisioned, delays, waiting = user_access_series(rows)

    assert steps == [0, 1]
    assert provisioned == [0, 1]
    assert delays == [0, 2.0]
    assert waiting == [0, 0]


def test_a_user_that_asked_and_was_not_served_is_waiting():
    rows = [
        {"Step": 0, "metrics": [user(1, access(True, False))]},
        {"Step": 1, "metrics": [user(1, access(True, False))]},
    ]

    _, provisioned, _, waiting = user_access_series(rows)

    assert provisioned == [0, 0]
    assert waiting == [0, 1]


def test_an_unreachable_application_adds_no_delay():
    """A flow with no path reports an infinite delay; summing it would swamp the figure."""
    rows = [
        {"Step": 0, "metrics": [user(1, access(True, True))]},
        {"Step": 1, "metrics": [user(1, access(True, True, delay=INFINITE))]},
    ]

    _, provisioned, delays, _ = user_access_series(rows)

    assert provisioned == [0, 1]
    assert delays == [0, 0]


def test_repetitions_are_averaged_over_the_steps_they_share():
    averaged = average_runs([([0, 1, 2], [2, 4, 6]), ([0, 1], [4, 8])])

    assert averaged == ([0, 1], [3.0, 6.0])


def test_migrations_count_applications_with_a_recorded_move():
    steps, migrations = migration_series(application_rows([0, 2, 3]))

    assert steps == [0, 1, 2]
    assert migrations == [0, 2, 3]


def test_resource_use_is_the_mean_of_the_hosted_applications():
    steps, cpu, memory = resource_series(application_rows([0, 2]))

    assert steps == [0, 1]
    assert cpu == [0, 10.0]
    assert memory == [0, 20.0]


def test_station_delay_follows_only_the_users_on_that_station():
    rows = [
        {
            "Step": 0,
            "metrics": [
                user(1, access(True, True, delay=3.0), access_points=["GroundStation_1"]),
                user(2, access(True, True, delay=7.0), access_points=["Satellite_4"]),
            ],
        }
    ]

    assert station_delay_series(rows, station_id=1) == ([0], [3.0])


def test_station_links_count_the_satellites_linked_to_it():
    rows = [
        {
            "Step": 0,
            "metrics": [
                {"Nodes": ["Satellite_1", "GroundStation_1"]},
                {"Nodes": ["Satellite_2", "GroundStation_1"]},
                {"Nodes": ["Satellite_2", "GroundStation_2"]},
                {"Nodes": ["ProcessUnit_9", "GroundStation_1"]},
            ],
        }
    ]

    assert station_link_series(rows, station_id=1) == ([0], [2])


def test_a_user_is_provisioned_from_its_second_step_in_the_topology_figure():
    rows = [
        {"Step": 0, "metrics": [user(1, access(True, True))]},
        {"Step": 1, "metrics": [user(1, access(True, True))]},
    ]

    assert provisioned_series(rows) == ([0, 1], [0, 1])


def test_each_topology_is_read_from_its_own_runs():
    """A topology's line comes from that topology's runs alone, so two topologies can differ."""
    with tempfile.TemporaryDirectory() as logs:
        write_run(
            os.path.join(logs, "rnp", "best_fit", "hybrid", "rep1"), "Application.jsonl", application_rows([1, 4])
        )
        write_run(
            os.path.join(logs, "geant", "best_fit", "hybrid", "rep1"), "Application.jsonl", application_rows([1, 2])
        )

        series = RunLogs(logs, ["best_fit"], "hybrid", 1).average_by_topology("Application.jsonl", migration_series)

    assert series == {"geant": ([0, 1], [1.0, 2.0]), "rnp": ([0, 1], [1.0, 4.0])}


def test_a_missing_repetition_is_skipped_rather_than_failing_the_figure():
    with tempfile.TemporaryDirectory() as logs:
        write_run(os.path.join(logs, "best_fit", "hybrid", "rep1"), "Application.jsonl", application_rows([2]))

        averages = RunLogs(logs, ["best_fit"], "hybrid", 2).average_by_algorithm("Application.jsonl", migration_series)

    assert averages == {"best_fit": ([0], [2.0])}


# -- Writing the figures ---------------------------------------------------------


def test_every_figure_is_written():
    with tempfile.TemporaryDirectory() as logs:
        topology = os.path.join(logs, "rnp")
        for rep in (1, 2):
            run = os.path.join(topology, "best_fit", "hybrid", f"rep{rep}")
            write_run(run, "User.jsonl", user_rows([0, 1, 2]))
            write_run(run, "Application.jsonl", application_rows([0, 1, 2]))
            write_run(
                run, "NetworkLink.jsonl", [{"Step": 0, "metrics": [{"Nodes": ["Satellite_1", "GroundStation_1"]}]}]
            )

        compare_algorithms_averaged(["best_fit"], ["hybrid"], 2, topology)
        plot_migrations(["best_fit"], ["hybrid"], 2, topology)
        plot_avg_resource_consumption(["best_fit"], ["hybrid"], 2, topology)
        plot_delay_by_groundstation(["best_fit"], ["hybrid"], 2, topology, ground_station_id=1)
        plot_groundstation_links_by_id(["best_fit"], ["hybrid"], 2, topology, ground_station_id=1)
        plot_avg_topology(["best_fit"], ["hybrid"], 2, logs)
        plot_provisioned_in_topology(["best_fit"], ["hybrid"], 2, logs)

        written = sorted(name for _, _, files in os.walk(logs) for name in files if name.endswith(".png"))

    assert written == sorted(
        [
            "avg_cpu_hybrid.png",
            "avg_memory_hybrid.png",
            "avg_migrations_topology_vs_step_hybrid.png",
            "avg_provisioned_topology_vs_step_hybrid.png",
            "delay_gs_1_hybrid.png",
            "delay_hybrid.png",
            "gs_1_links_hybrid.png",
            "migrations_hybrid.png",
            "not_provisioned_hybrid.png",
            "provisioned_hybrid.png",
        ]
    )


def test_the_station_figures_follow_the_station_asked_for():
    links = partial(station_link_series, station_id=2)
    rows = [{"Step": 0, "metrics": [{"Nodes": ["Satellite_1", "GroundStation_2"]}]}]

    assert links(rows) == ([0], [1])


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
