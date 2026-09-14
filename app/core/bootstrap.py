"""Building a simulator from a configuration."""

import random

import dataset as ds
from leosim import ComponentManager, Simulator, default_topology_management
from leosim.components import Satellite
from leosim.components.allocation_algorithms import best_fit_allocation, longest_duration_allocation

DEFAULT_SCENARY_PATH = "datasets/temp_dashboard_scenary.json"
DEFAULT_LOGS_DIRECTORY = "logs/dashboard"

# Fixed seed so that two runs of the same configuration produce the same
# scenario. It seeds the process-wide generator, which is what the helpers in
# `dataset.py` draw from.
RANDOM_SEED = 42

ALLOCATION_ALGORITHMS = {
    "best_fit_allocation": best_fit_allocation,
    "longest_duration_allocation": longest_duration_allocation,
}


def clear_components():
    """Resets the instance registry of every engine component.

    Required before assembling a new scenario, because each component class
    keeps its own instance list in a class attribute.
    """
    for component_class in ComponentManager.__subclasses__():
        if component_class.__name__ != "Simulator":
            component_class.clear()


def resolve_algorithm(name):
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
            f"Unknown allocation algorithm: {name!r}. Available: {sorted(ALLOCATION_ALGORITHMS)}."
        )
    return ALLOCATION_ALGORITHMS[name]


def distribute_process_units(topology, scenario):
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


def build_scenario(config, scenary_path=DEFAULT_SCENARY_PATH):
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


def build_simulator(config, scenary_path=DEFAULT_SCENARY_PATH, logs_directory=DEFAULT_LOGS_DIRECTORY):
    """Builds a simulator ready to run.

    Args:
        config (SimulationConfig): Simulation configuration.
        scenary_path (str): Where to write the intermediate scenario file.
        logs_directory (str): Directory the simulator writes metrics to.

    Returns:
        Simulator: A simulator initialized at step zero.
    """
    algorithm = resolve_algorithm(config.algorithm)
    scenary_file = build_scenario(config, scenary_path=scenary_path)

    simulator = Simulator(
        stopping_criterion=lambda model: False,
        resource_management_algorithm=algorithm,
        topology_management_algorithm=default_topology_management,
        clean_data_in_memory=False,
        logs_directory=logs_directory,
        scenario=config.scenario,
    )
    simulator.initialize(scenary_file)
    return simulator
