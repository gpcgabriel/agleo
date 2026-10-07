import argparse
import os
import random
import shutil
from collections.abc import Callable

import dataset as ds
from app.agents.allocation import LLMAllocator
from app.core.bootstrap import ALLOCATION_ALGORITHMS, distribute_process_units
from leosim import ComponentManager, Simulator, clear_components
from leosim.components import default_topology_management

DATASETS_DIR = "datasets"


def build_stopping_criterion(num_steps: int) -> Callable[[Simulator], bool]:
    """Returns a criterion that stops a simulation once it has run `num_steps` ticks."""
    return lambda model: model.scheduler.steps == num_steps


def main(args):
    os.makedirs(DATASETS_DIR, exist_ok=True)

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

        log_dir = os.path.join(args.logs_dir, args.algorithm, scenario, f"rep{rep}")
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

    args = parser.parse_args()
    if not args.llm and args.algorithm is None:
        parser.error("--algorithm is required unless --llm is given.")

    main(args)
