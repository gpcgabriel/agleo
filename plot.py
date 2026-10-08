"""Plots of the metrics `main.py` writes, comparing algorithms and topologies.

`main.py` writes each run to `<logs>/<topology>/<algorithm>/<scenario>/rep<n>/`, one JSON
Lines file per component class, with a row per step holding every instance's metrics.

Each figure is computed by one function and drawn by another, so what a figure shows can be
tested without drawing it. A series is the steps of a run followed by one or more columns of
values measured at those steps.
"""

import json
import os
from collections.abc import Callable, Iterable, Iterator
from functools import partial
from pathlib import Path
from typing import Any

from matplotlib.figure import Figure

MARKERS = ["o", "x", "s", "^", "D", "*", "v", "+"]

# Naming one row of a metrics file: {"Step": n, "metrics": [one dictionary per instance]}.
Row = dict[str, Any]
Series = tuple[list[float], ...]
# Naming the steps of a run paired with one column of values.
Column = tuple[list[float], list[float]]
Extractor = Callable[[Iterable[Row]], Series]


def read_jsonl(file_path: str) -> Iterator[Row]:
    """Yields each row of a JSON Lines file."""
    with open(file_path, encoding="utf-8") as file:
        for line in file:
            yield json.loads(line)


def calculate_average(list_of_lists: list[list[float]]) -> list[float]:
    """Returns the element-wise average of several series, cut to the shortest of them."""
    if not list_of_lists:
        return []

    shortest = min(len(values) for values in list_of_lists)
    return [sum(values[index] for values in list_of_lists) / len(list_of_lists) for index in range(shortest)]


def average_runs(runs: list[Series]) -> Series:
    """Averages repetitions of the same series, column by column, over the steps they share.

    Args:
        runs (list): One series per repetition, all with the same columns.

    Returns:
        tuple: The first repetition's steps, cut to the shortest repetition, then each
        column averaged.
    """
    columns = [calculate_average([run[column] for run in runs]) for column in range(1, len(runs[0]))]
    return (runs[0][0][: len(columns[0])], *columns)


def columns_of(averages: dict[str, Series], column: int) -> dict[str, Column]:
    """Returns, per label, the steps paired with one column of its averaged series."""
    return {label: (series[0], series[column]) for label, series in averages.items()}


def get_topologies(current_path: str) -> list[str]:
    """Returns the names of the topology directories under a logs directory, sorted."""
    return sorted(
        path.name
        for path in Path(current_path).iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name != "__pycache__"
    )


def build_path(current_path: str, algorithm: str, scenario: str, filename: str, rep: int = 1) -> str:
    """Returns the path of one metrics file of one repetition."""
    return os.path.join(current_path, algorithm, scenario, f"rep{rep}", filename)


class RunLogs:
    """The metrics files that runs of some algorithms, in one scenario, wrote under one directory."""

    def __init__(self, current_path: str, algorithm_names: list[str], scenario: str, num_repetitions: int) -> None:
        """Args:
        current_path (str): The directory holding one directory per algorithm.
        algorithm_names (list): The algorithms to read, in the order the plots list them.
        scenario (str): The scenario the runs simulated.
        num_repetitions (int): How many repetitions each algorithm ran.
        """
        self.current_path = current_path
        self.algorithm_names = algorithm_names
        self.scenario = scenario
        self.num_repetitions = num_repetitions

    def files(self, algorithm: str, filename: str) -> Iterator[str]:
        """Yields the file of each repetition that exists, warning about each that does not."""
        for rep in range(1, self.num_repetitions + 1):
            file_path = build_path(self.current_path, algorithm, self.scenario, filename, rep)
            if not os.path.isfile(file_path):
                print(f"WARNING: {file_path} not found")
                continue
            yield file_path

    def average_by_algorithm(self, filename: str, extract: Extractor) -> dict[str, Series]:
        """Returns, per algorithm, the series `extract` reads from each repetition, averaged.

        A repetition whose file holds no rows is left out, and an algorithm with no
        repetition left is absent from the result.
        """
        averages = {}
        for algorithm in self.algorithm_names:
            runs = [run for run in (extract(read_jsonl(path)) for path in self.files(algorithm, filename)) if run[0]]
            if runs:
                averages[algorithm] = average_runs(runs)
        return averages

    def average_by_topology(self, filename: str, extract: Extractor) -> dict[str, Column]:
        """Returns, per topology directory, the values `extract` reads, averaged step by step.

        Every algorithm and repetition of a topology is pooled into one line, so the
        figure compares the topologies rather than the algorithms.
        """
        series_by_topology = {}
        for topology in get_topologies(self.current_path):
            topology_logs = RunLogs(
                os.path.join(self.current_path, topology), self.algorithm_names, self.scenario, self.num_repetitions
            )
            values_by_step = {}
            for algorithm in self.algorithm_names:
                for path in topology_logs.files(algorithm, filename):
                    steps, values = extract(read_jsonl(path))
                    for step, value in zip(steps, values, strict=True):
                        values_by_step.setdefault(step, []).append(value)

            if values_by_step:
                steps = sorted(values_by_step)
                series_by_topology[topology] = (steps, [sum(values_by_step[s]) / len(values_by_step[s]) for s in steps])
        return series_by_topology


def plot(series_by_label: dict[str, Column], xlabel: str, ylabel: str, output_path: str) -> None:
    """Draws one line per labelled series and saves the figure as a PNG.

    Args:
        series_by_label (dict): Label to (steps, values).
        xlabel (str): Horizontal axis label.
        ylabel (str): Vertical axis label.
        output_path (str): Where to write the PNG.
    """
    figure = Figure(figsize=(12, 7))
    axes = figure.subplots()

    for index, (label, (steps, values)) in enumerate(series_by_label.items()):
        axes.plot(steps, values, label=label, marker=MARKERS[index % len(MARKERS)])

    axes.set_xlabel(xlabel, fontsize=18)
    axes.set_ylabel(ylabel, fontsize=18)
    axes.tick_params(labelsize=18)
    axes.grid(True)
    axes.legend(fontsize=15)

    figure.savefig(output_path)


# -- Reading the series out of the metric rows ---------------------------------


def user_access_series(rows: Iterable[Row]) -> Series:
    """Returns, per step, the users served, their summed delay and the users left waiting.

    Each user's first application is compared with its own previous step, so a user is
    counted from its second appearance on.
    """
    steps = []
    provisioned = []
    delays = []
    waiting = []
    last_accesses = {}

    for data in rows:
        step_provisioned, step_delay, step_waiting = count_user_accesses(data["metrics"], last_accesses)
        steps.append(data["Step"])
        provisioned.append(step_provisioned)
        delays.append(step_delay)
        waiting.append(step_waiting)

    return steps, provisioned, delays, waiting


def count_user_accesses(metrics: list[Row], last_accesses: dict[int, Row]) -> tuple[int, float, int]:
    """Counts one step's served users, their summed delay and the users left waiting.

    Args:
        metrics (list): The users' metric rows of the step.
        last_accesses (dict): Each user's first application at the step before, updated here.

    Returns:
        tuple: (users served, their summed delay, users left waiting).
    """
    provisioned, delay, waiting = 0, 0, 0

    for metric in metrics:
        current = metric["Access to Applications"][0]
        last = last_accesses.get(metric["ID"])
        last_accesses[metric["ID"]] = current
        if last is None:
            continue

        if last["Request Provisioning"] and not current["Is Provisioned"]:
            waiting += 1
        elif current["Is Provisioned"] or current["Provisioning"]:
            provisioned += 1
            if current["Delay"] != float("inf"):
                delay += current["Delay"]

    return provisioned, delay, waiting


def provisioned_series(rows: Iterable[Row]) -> Series:
    """Returns, per step, the users whose application is provisioned, from each user's second appearance on."""
    steps = []
    provisioned = []
    seen = set()

    for data in rows:
        step_provisioned = 0
        for metric in data["metrics"]:
            current = metric["Access to Applications"][0]
            if metric["ID"] in seen and (current["Is Provisioned"] or current.get("Provisioning")):
                step_provisioned += 1
            seen.add(metric["ID"])

        steps.append(data["Step"])
        provisioned.append(step_provisioned)

    return steps, provisioned


def migration_series(rows: Iterable[Row]) -> Series:
    """Returns, per step, the applications whose last migration names an origin and a target."""
    steps = []
    migrations = []

    for data in rows:
        steps.append(data["Step"])
        migrations.append(
            sum(
                1
                for metric in data["metrics"]
                if metric.get("Last Migration")
                and metric["Last Migration"].get("origin") is not None
                and metric["Last Migration"].get("target") is not None
            )
        )

    return steps, migrations


def resource_series(rows: Iterable[Row]) -> Series:
    """Returns, per step, the mean CPU and memory demand of the applications hosted and available."""
    cpu_by_step = {}
    memory_by_step = {}
    applications_by_step = {}

    for data in rows:
        step = data["Step"]
        cpu_by_step.setdefault(step, 0)
        memory_by_step.setdefault(step, 0)
        applications_by_step.setdefault(step, 0)
        for metric in data["metrics"]:
            if metric.get("Process Unit") and metric.get("Available"):
                cpu_by_step[step] += metric.get("CPU Demand", 0)
                memory_by_step[step] += metric.get("Memory Demand", 0)
                applications_by_step[step] += 1

    steps = sorted(cpu_by_step)
    return (
        steps,
        [cpu_by_step[step] / applications_by_step[step] if applications_by_step[step] else 0 for step in steps],
        [memory_by_step[step] / applications_by_step[step] if applications_by_step[step] else 0 for step in steps],
    )


def station_delay_series(rows: Iterable[Row], station_id: int) -> Series:
    """Returns, per step, the summed delay of the provisioned applications of the users on one station."""
    station = f"GroundStation_{station_id}"
    steps = []
    delays = []

    for data in rows:
        step_delay = 0
        for metric in data["metrics"]:
            if station not in metric.get("Network Access Points", []):
                continue
            current = metric["Access to Applications"][0]
            if current["Is Provisioned"] or current.get("Provisioning"):
                delay = current.get("Delay", 0)
                if delay is not None and delay != float("inf"):
                    step_delay += delay

        steps.append(data["Step"])
        delays.append(step_delay)

    return steps, delays


def station_link_series(rows: Iterable[Row], station_id: int) -> Series:
    """Returns, per step, how many satellites hold a link with one station."""
    station = f"GroundStation_{station_id}"
    steps = []
    satellites = []

    for data in rows:
        steps.append(data["Step"])
        satellites.append(
            sum(
                1
                for link in data["metrics"]
                if station in link["Nodes"] and any(node.startswith("Satellite_") for node in link["Nodes"])
            )
        )

    return steps, satellites


# -- Drawing the figures ---------------------------------------------------------


def compare_algorithms_averaged(
    algorithm_names: list[str], scenarios: list[str], num_repetitions: int, current_path: str
) -> None:
    """Plots, per scenario, the users served, their delay and the users left waiting, one line per algorithm."""
    for scenario in scenarios:
        print(f"Processing scenario: {scenario}")
        logs = RunLogs(current_path, algorithm_names, scenario, num_repetitions)
        averages = logs.average_by_algorithm("User.jsonl", user_access_series)

        for column, ylabel, filename in (
            (1, "Avg Number of Provisioned Applications", f"provisioned_{scenario}.png"),
            (2, "Delay", f"delay_{scenario}.png"),
            (3, "Avg Applications Not Provisioned", f"not_provisioned_{scenario}.png"),
        ):
            plot(columns_of(averages, column), "Step", ylabel, os.path.join(current_path, filename))


def plot_migrations(algorithm_names: list[str], scenarios: list[str], num_repetitions: int, current_path: str) -> None:
    """Plots, per scenario, the migrations of each step, one line per algorithm."""
    for scenario in scenarios:
        print(f"Processing migrations for scenario: {scenario}")
        averages = RunLogs(current_path, algorithm_names, scenario, num_repetitions).average_by_algorithm(
            "Application.jsonl", migration_series
        )
        output_path = os.path.join(current_path, f"migrations_{scenario}.png")
        plot(columns_of(averages, 1), "Step", "Avg Number of Migrations", output_path)


def plot_avg_topology(
    algorithm_names: list[str], scenarios: list[str], num_repetitions: int, current_path: str
) -> None:
    """Plots, per scenario, the migrations of each step, one line per topology under `current_path`."""
    for scenario in scenarios:
        series = RunLogs(current_path, algorithm_names, scenario, num_repetitions).average_by_topology(
            "Application.jsonl", migration_series
        )
        output_path = os.path.join(current_path, f"avg_migrations_topology_vs_step_{scenario}.png")
        plot(series, "Step", "Avg Number of Migrations", output_path)


def plot_provisioned_in_topology(
    algorithm_names: list[str], scenarios: list[str], num_repetitions: int, current_path: str
) -> None:
    """Plots, per scenario, the users served at each step, one line per topology under `current_path`."""
    for scenario in scenarios:
        series = RunLogs(current_path, algorithm_names, scenario, num_repetitions).average_by_topology(
            "User.jsonl", provisioned_series
        )
        output_path = os.path.join(current_path, f"avg_provisioned_topology_vs_step_{scenario}.png")
        plot(series, "Step", "Avg Number of Provisioned Users", output_path)


def plot_groundstation_links_by_id(
    algorithm_names: list[str], scenarios: list[str], num_repetitions: int, current_path: str, ground_station_id: int
) -> None:
    """Plots, per scenario, how many satellites one station is linked to, one line per algorithm."""
    for scenario in scenarios:
        print(f"Processing GroundStation {ground_station_id} scenario: {scenario}")
        averages = RunLogs(current_path, algorithm_names, scenario, num_repetitions).average_by_algorithm(
            "NetworkLink.jsonl", partial(station_link_series, station_id=ground_station_id)
        )
        ylabel = f"Number of satellites connected to GroundStation_{ground_station_id}"
        output_path = os.path.join(current_path, f"gs_{ground_station_id}_links_{scenario}.png")
        plot(columns_of(averages, 1), "Step", ylabel, output_path)


def plot_delay_by_groundstation(
    algorithm_names: list[str], scenarios: list[str], num_repetitions: int, current_path: str, ground_station_id: int
) -> None:
    """Plots, per scenario, the delay of the users served through one station, one line per algorithm."""
    for scenario in scenarios:
        print(f"Processing delay for GS {ground_station_id} - scenario: {scenario}")
        averages = RunLogs(current_path, algorithm_names, scenario, num_repetitions).average_by_algorithm(
            "User.jsonl", partial(station_delay_series, station_id=ground_station_id)
        )
        output_path = os.path.join(current_path, f"delay_gs_{ground_station_id}_{scenario}.png")
        plot(columns_of(averages, 1), "Step", f"Delay (GS {ground_station_id})", output_path)


def plot_avg_resource_consumption(
    algorithm_names: list[str], scenarios: list[str], num_repetitions: int, current_path: str
) -> None:
    """Plots, per scenario, the mean CPU and memory of the hosted applications, one line per algorithm."""
    for scenario in scenarios:
        print(f"Processing resource consumption - scenario: {scenario}")
        averages = RunLogs(current_path, algorithm_names, scenario, num_repetitions).average_by_algorithm(
            "Application.jsonl", resource_series
        )
        cpu_path = os.path.join(current_path, f"avg_cpu_{scenario}.png")
        memory_path = os.path.join(current_path, f"avg_memory_{scenario}.png")
        plot(columns_of(averages, 1), "Step", "Avg CPU Consumption per Application", cpu_path)
        plot(columns_of(averages, 2), "Step", "Avg Memory Consumption per Application", memory_path)
