import argparse
import os
import random
import shutil
from collections.abc import Callable
from pathlib import Path

import dataset as ds
from app.agents.allocation import LLMAllocator
from app.core.bootstrap import ALLOCATION_ALGORITHMS, distribute_process_units
from leosim import ComponentManager, Simulator, clear_components
from leosim.components import default_topology_management
from plot import (
    compare_algorithms_averaged,
    plot_avg_resource_consumption,
    plot_avg_topology,
    plot_delay_by_groundstation,
    plot_groundstation_links_by_id,
    plot_migrations,
    plot_provisioned_in_topology,
)

DATASETS_DIR = "datasets"


def build_stopping_criterion(num_steps: int) -> Callable[[Simulator], bool]:
    """Returns a criterion that stops a simulation once it has run `num_steps` ticks."""
    return lambda model: model.scheduler.steps == num_steps


def plot_results(logs_dir: str, topology_name: str, scenario: str, num_repetitions: int, station_id: int) -> None:
    """Plots every algorithm that has run on this topology and scenario, then compares the topologies.

    Args:
        logs_dir (str): The directory holding one directory per topology.
        topology_name (str): The topology the runs just made used.
        scenario (str): The scenario they simulated.
        num_repetitions (int): How many repetitions each algorithm ran.
        station_id (int): The ground station the per-station figures follow.
    """
    topology_logs = os.path.join(logs_dir, topology_name)
    algorithms = sorted(entry.name for entry in os.scandir(topology_logs) if entry.is_dir())
    scenarios = [scenario]

    compare_algorithms_averaged(algorithms, scenarios, num_repetitions, topology_logs)
    plot_migrations(algorithms, scenarios, num_repetitions, topology_logs)
    plot_avg_resource_consumption(algorithms, scenarios, num_repetitions, topology_logs)
    plot_delay_by_groundstation(algorithms, scenarios, num_repetitions, topology_logs, station_id)
    plot_groundstation_links_by_id(algorithms, scenarios, num_repetitions, topology_logs, station_id)
    plot_avg_topology(algorithms, scenarios, num_repetitions, logs_dir)
    plot_provisioned_in_topology(algorithms, scenarios, num_repetitions, logs_dir)


def main(args: argparse.Namespace) -> None:
    os.makedirs(DATASETS_DIR, exist_ok=True)

    # Naming the runs after the topology file, so runs on different topologies sit side by side.
    topology_name = Path(args.dataset).stem

    # Building the LLM allocator here rather than naming it in ALLOCATION_ALGORITHMS:
    # the engine must not import the agent package, so the CLI assembles it the way
    # the dashboard's sidebar does.
    if args.llm:
        args.algorithm = "llm_allocation"
        algorithm = LLMAllocator(model_name=args.model).allocate
    else:
        algorithm = ALLOCATION_ALGORITHMS[args.algorithm]

    for rep in range(1, args.repetitions + 1):
        print(f"\n--- Repetition {rep}/{args.repetitions} ---")

        scenario = args.scenario

        # Generating this repetition's dataset from its own seed.
        clear_components()
        random.seed(rep)

        print(f"  Generating Dataset: {scenario}")

        topology = ds.load_topology(args.dataset, args.satellites, args.num_satellites)
        ds.create_users(args.num_users)
        distribute_process_units(topology, scenario)
        ds.configure_mobility_models()

        dataset_file = os.path.join(DATASETS_DIR, f"dataset_rep{rep}_{scenario}.json")
        ComponentManager.save_scenary(filename=dataset_file)

        # Executing the simulation over that dataset.
        print(f"  Executing Algorithm: {args.algorithm}")

        log_dir = os.path.join(args.logs_dir, topology_name, args.algorithm, scenario, f"rep{rep}")
        if os.path.exists(log_dir):
            shutil.rmtree(log_dir)
        os.makedirs(log_dir, exist_ok=True)

        sim = Simulator(
            stopping_criterion=build_stopping_criterion(args.num_steps),
            resource_management_algorithm=algorithm,
            topology_management_algorithm=default_topology_management,
            ignore_list=[],
            clean_data_in_memory=True,
            logs_directory=log_dir,
        )

        sim.initialize(dataset_file)
        sim.run()

    if args.plot:
        plot_results(args.logs_dir, topology_name, args.scenario, args.repetitions, args.plot_station)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LEO Simulation Runner")

    parser.add_argument("--dataset", required=True)
    parser.add_argument("--satellites", required=True)
    parser.add_argument("--algorithm", choices=ALLOCATION_ALGORITHMS.keys())
    parser.add_argument("--scenario", required=True, choices=["terrestrial", "leo", "hybrid"])
    parser.add_argument("--num_users", type=int, default=100)
    parser.add_argument("--num_satellites", type=int, default=25)
    parser.add_argument("--num_steps", type=int, default=15)
    parser.add_argument("--logs_dir", default="logs")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--llm", action="store_true", help="Enable the LLM allocator in each ground station")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model the LLM allocator asks")
    parser.add_argument(
        "--plot", action="store_true", help="Plot every algorithm run on this topology and scenario once the runs end"
    )
    parser.add_argument("--plot_station", type=int, default=1, help="Ground station the per-station plots follow")

    args = parser.parse_args()
    if not args.llm and args.algorithm is None:
        parser.error("--algorithm is required unless --llm is given.")

    main(args)
