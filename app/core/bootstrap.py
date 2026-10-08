"""Building a simulator from a configuration."""

from __future__ import annotations

import os
import random
import tempfile
from typing import TYPE_CHECKING

import dataset as ds
from leosim import ComponentManager, Simulator, clear_components
from leosim.components import Satellite, best_fit_allocation, default_topology_management, longest_duration_allocation

if TYPE_CHECKING:
    from app.core.config import SimulationConfig
    from leosim.components import Topology
    from leosim.simulator import AllocationAlgorithm

DEFAULT_LOGS_DIRECTORY = "logs/dashboard"

# Fixing the seed so two runs of the same configuration produce the same
# scenario. It seeds the process-wide generator, which is what the helpers in
# `dataset.py` draw from.
RANDOM_SEED = 42

ALLOCATION_ALGORITHMS = {
    "best_fit_allocation": best_fit_allocation,
    "longest_duration_allocation": longest_duration_allocation,
}


def resolve_algorithm(name: str) -> AllocationAlgorithm:
    """Maps an allocation algorithm name to its function.

    Args:
        name (str): Algorithm name.

    Returns:
        Callable: The algorithm function.

    Raises:
        ValueError: If the name is not registered.
    """
    if name not in ALLOCATION_ALGORITHMS:
        raise ValueError(
            f"Unknown allocation algorithm: {name!r}. Available: {sorted(ALLOCATION_ALGORITHMS)}. "
            "Algorithms outside this registry must be passed to build_simulator directly."
        )
    return ALLOCATION_ALGORITHMS[name]


def distribute_process_units(topology: Topology, scenario: str) -> None:
    """Distributes process units according to the chosen scenario.

    Args:
        topology: The terrestrial topology, already loaded.
        scenario (str): "terrestrial", "leo" or "hybrid".
    """
    total_resources = Satellite.count()

    if scenario == "terrestrial":
        ds.add_process_unit_to_ground_stations(topology, num_process_units=total_resources)
    elif scenario == "leo":
        ds.add_process_unit_to_satellites(topology, num_process_units=total_resources)
    elif scenario == "hybrid":
        ds.add_process_unit_to_ground_stations(topology, num_process_units=total_resources)
        ds.add_process_unit_to_satellites(topology, num_process_units=total_resources)


def build_scenario(config: SimulationConfig, scenary_path: str) -> str:
    """Assembles the scenario in memory and writes it to disk.

    Args:
        config (SimulationConfig): Simulation configuration.
        scenary_path (str): Where to write the generated scenario file.

    Returns:
        str: The path of the written scenario.
    """
    clear_components()
    random.seed(RANDOM_SEED)

    topology = ds.load_topology(
        ground_topology=config.gml_path,
        leo_topology=config.satellites_path,
        max_satellites=config.num_satellites,
    )
    ds.create_users(config.num_users)
    distribute_process_units(topology, config.scenario)
    ds.configure_mobility_models()

    ComponentManager.save_scenary(filename=scenary_path)
    return scenary_path


def build_simulator(
    config: SimulationConfig,
    scenary_path: str | None = None,
    logs_directory: str = DEFAULT_LOGS_DIRECTORY,
    allocation_algorithm: AllocationAlgorithm | None = None,
) -> Simulator:
    """Builds a simulator ready to run.

    Args:
        config (SimulationConfig): Simulation configuration.
        scenary_path (str, optional): Where to write the intermediate scenario file. When None, it
            goes to a private temporary file, removed once the simulator has read it.
        logs_directory (str): Directory the simulator writes metrics to.
        allocation_algorithm (Callable): Allocation strategy to inject. When
            None, it is resolved from `config.algorithm`. The composition root
            passes strategies this layer must not import, such as the
            LLM-driven allocator.

    Returns:
        Simulator: A simulator initialized at step zero.
    """
    algorithm = allocation_algorithm or resolve_algorithm(config.algorithm)

    with tempfile.TemporaryDirectory(prefix="agleo-scenario-") as directory:
        # Writing to a private file when the caller names none: the dashboard and a test run building
        # simulators at the same moment would otherwise read each other's scenario.
        scenary_file = build_scenario(config, scenary_path or os.path.join(directory, "scenario.json"))

        simulator = Simulator(
            resource_management_algorithm=algorithm,
            topology_management_algorithm=default_topology_management,
            logs_directory=logs_directory,
            scenario=config.scenario,
        )
        simulator.initialize(scenary_file)

    return simulator
