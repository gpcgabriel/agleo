"""The simulator: loads a scenario from a file and runs it tick by tick."""

from __future__ import annotations

import datetime
import json
import os
from collections.abc import Callable
from typing import Any

from .component_manager import ComponentManager
from .components import (
    GroundStation,
    NetworkLink,
    ProcessUnit,
    Satellite,
    Topology,
    coordinates_history,
    default_topology_management,
    deterministic_failure_model,
    linear_estimation,
    random_failure_model,
    random_mobility_model,
)
from .scheduler import Scheduler

# Naming the functions a scenario file may refer to, which are the models a component runs:
# `save_scenary` writes a model by its `__name__`, and `initialize` reads it back from here.
SCENARIO_FUNCTIONS = {
    function.__name__: function
    for function in (
        coordinates_history,
        linear_estimation,
        random_mobility_model,
        deterministic_failure_model,
        random_failure_model,
    )
}


class Simulator(ComponentManager):
    """Orchestrates the internal operations of the simulation tool.

    This class manages agent scheduling, initialization, data collection,
    and storage processes. It acts as the central controller for the
    simulation lifecycle.

    Attributes:
        _instances (list): List of active Simulator instances.
        _object_count (int): Counter for the number of created objects.
        time_units (list): Supported time units for conversion.
    """

    _instances = []
    _object_count = 0

    time_units = ["seconds", "minutes", "hours"]

    # Leaving the simulator out of the scenario file: it loads the file rather than belonging to it.
    saved_in_scenario = False

    # Declaring the provisionings per step that `longest_duration_allocation` counts on the simulator,
    # creating the attribute on its first run.
    provisioning_history: dict[str, int]

    def __init__(
        self,
        id: int = 0,
        stopping_criterion: Callable[[Simulator], bool] | None = None,
        resource_management_algorithm: AllocationAlgorithm | None = None,
        resource_management_algorithm_parameters: dict[str, Any] | None = None,
        topology_management_algorithm: Callable[..., None] = default_topology_management,
        topology_management_algorithm_parameters: dict[str, Any] | None = None,
        user_defined_functions: list[Callable[..., Any]] | None = None,
        scheduler: type[Scheduler] = Scheduler,
        dump_interval: int = 100,
        logs_directory: str = "logs",
        ignore_list: list[type[ComponentManager]] | None = None,
        clean_data_in_memory: bool = False,
        tick_duration: int = 1,
        time_unit: str = "seconds",
        scenario: str = "hybrid",
        repetition: int = 1,
        topology_name: str | None = None,
    ) -> None:
        """Initializes a new Simulator instance.

        Args:
            id (int): Unique identifier for the simulator. Defaults to 0.
            stopping_criterion (Callable): Binary function that returns True
                when the simulation should terminate.
            resource_management_algorithm (Callable): Function implementing
                provisioning and migration policies.
            resource_management_algorithm_parameters (dict): Parameters
                passed to the resource management function.
            topology_management_algorithm (Callable): Function implementing
                link addition and removal logic.
            topology_management_algorithm_parameters (dict): Parameters
                passed to the topology management function.
            user_defined_functions (list): List of user functions to be
                injected into the global namespace.
            scheduler (Class): Scheduler class used for component execution.
            dump_interval (int): Tick interval for writing logs to disk.
            logs_directory (str): Path where log files will be stored.
            ignore_list (list): List of agent classes to exclude from metrics.
            clean_data_in_memory (bool): If True, clears metric lists after
                each disk dump.
            tick_duration (int): Duration value for time conversion.
            time_unit (str): Unit of time (e.g., 'seconds', 'hours').
            scenario (str): Scenario label for experiment differentiation.
            repetition (int): Repetition index for the current simulation.
            topology_name (str): Name or type of the network topology.
        """
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        if id == 0:
            id = self.__class__._object_count
        self.id = id

        self.stopping_criterion = stopping_criterion
        self.running = False

        if resource_management_algorithm is not None and not callable(resource_management_algorithm):
            raise TypeError(
                f"resource_management_algorithm must be callable or None, got "
                f"{resource_management_algorithm!r}. A non-callable value would leave every tick "
                f"without allocation and say nothing."
            )
        self.resource_management_algorithm = resource_management_algorithm

        # Copying the parameters into a fresh dictionary: using the signature
        # default directly would make two instances share, and overwrite, the
        # same dictionary.
        self.resource_management_algorithm_parameters = dict(resource_management_algorithm_parameters or {})
        self.resource_management_algorithm_parameters["scenario"] = scenario

        self.topology_management_algorithm = topology_management_algorithm
        self.topology_management_parameters = dict(topology_management_algorithm_parameters or {})

        self.scheduler = scheduler(self)
        self.topology = Topology()

        self.logs_directory = logs_directory
        self.dump_interval = dump_interval
        self.last_dump = 0
        self.clean_data_in_memory = clean_data_in_memory
        self.agent_metrics = {}
        self.ignore_list = list(ignore_list or [])

        # Converting the time unit through timedelta, for a single standard.
        self.tick_duration = datetime.timedelta(**{time_unit: tick_duration}).total_seconds()

        # Adding the caller's own models to the ones a scenario file may name.
        self.scenario_functions = dict(SCENARIO_FUNCTIONS)
        for function in user_defined_functions or []:
            self.scenario_functions[function.__name__] = function

        ComponentManager.model = self

        self.scenario = scenario
        self.repetition = repetition
        self.topology_name = topology_name

    def initialize(self, dataset: str) -> None:
        """Initializes agents and their relationships from a JSON dataset.

        Args:
            dataset (str): File path to the JSON configuration file.

        Raises:
            FileNotFoundError: If the dataset path is invalid.
            json.JSONDecodeError: If the file is not a valid JSON.
        """
        clear_components()

        with open(dataset, encoding="UTF-8") as file:
            dataset_data = json.load(file)

        created_components = []

        # Instantiating the objects described by the dataset schema.
        for class_name, components in dataset_data.items():
            component_class = find_component_class(class_name)
            for component in components:
                obj = component_class()
                obj.set_attributes(**component)
                obj.relationships = component["relationships"]
                created_components.append(obj)

        # Resolving the relationships between objects.
        for obj in created_components:
            for key, value in obj.relationships.items():
                self.resolve_relationship(obj, key, value)

        # Adding the network nodes to the topology manager.
        for agent in GroundStation.all() + Satellite.all() + ProcessUnit.all():
            self.topology.add_node(agent)

        # Establishing the network links.
        for link in NetworkLink.all():
            self.topology.attach_link(link)

    def resolve_relationship(
        self, obj: ComponentManager, key: str, value: str | dict[str, Any] | list[dict[str, Any]] | None
    ) -> None:
        """Restores one relationship of a loaded component from what the scenario file recorded.

        A value that matches none of the recorded shapes leaves the attribute
        at its constructor default.

        Args:
            obj (ComponentManager): The component being restored.
            key (str): The attribute the relationship fills.
            value (str | dict | list | None): What the file holds: a model's name, a reference such as
                {"class": "User", "id": 3}, a mapping to model names, a list of
                references, or None.
        """
        functions = self.scenario_functions

        if isinstance(value, str) and value in functions:
            setattr(obj, key, functions[value])

        elif isinstance(value, dict) and "class" in value and "id" in value:
            setattr(obj, key, find_component_class(value["class"]).find_by("id", value["id"]))

        elif isinstance(value, dict) and all(name in functions for name in value.values()):
            setattr(obj, key, {label: functions[name] for label, name in value.items()})

        elif isinstance(value, list) and all("id" in reference and "class" in reference for reference in value):
            referenced = [find_component_class(ref["class"]).find_by("id", ref["id"]) for ref in value]
            setattr(obj, key, referenced)

        elif value is None:
            setattr(obj, key, None)

    def initialize_logs(self) -> None:
        """Sets up the directory and data structures for metric logging."""
        os.makedirs(self.logs_directory, exist_ok=True)

        for component_class in ComponentManager.__subclasses__():
            if (
                component_class not in [*self.ignore_list, self.__class__]
                and component_class.__name__ not in self.agent_metrics
            ):
                self.agent_metrics[component_class.__name__] = []

    def step(self) -> None:
        """Executes a single simulation tick.

        Updates the scheduler, topology management, and resource allocation.
        """
        self.scheduler.step()
        self.topology_management_algorithm(topology=self.topology, **self.topology_management_parameters)

        if self.resource_management_algorithm is not None:
            for gs in GroundStation.all():
                params = dict(self.resource_management_algorithm_parameters)
                params["ground_station"] = gs
                self.resource_management_algorithm(self, params)

    def monitor(self) -> None:
        """Collects metrics from all tracked components.

        Triggered every step. If the dump interval is reached, it invokes
        the data persistence method.
        """
        for component_class in ComponentManager.__subclasses__():
            if component_class not in self.ignore_list + [self.__class__]:
                metrics = {
                    "Step": self.scheduler.steps,
                    "metrics": component_class.collect_class_metrics(),
                }

                if not metrics["metrics"]:
                    continue

                self.agent_metrics[component_class.__name__].append(metrics)

        if self.scheduler.steps == self.last_dump + self.dump_interval:
            self.dump_data()
            self.last_dump = self.scheduler.steps

    def dump_data(self) -> None:
        """Writes accumulated metrics to JSONL files on disk.

        If `clean_data_in_memory` is True, the internal buffer is cleared
        after a successful write.
        """
        if not os.path.exists(self.logs_directory):
            os.makedirs(self.logs_directory)

        for agent_class, data in self.agent_metrics.items():
            filename = f"{self.logs_directory}/{agent_class}.jsonl"

            with open(filename, mode="a", encoding="utf-8") as file:
                for metric in data:
                    file.write(json.dumps(metric) + "\n")

            if self.clean_data_in_memory:
                self.agent_metrics[agent_class] = []

    def run(self) -> None:
        """Starts the main simulation execution loop.

        Runs until the `stopping_criterion` evaluates to True. Performs
        initial monitoring and a final data dump after termination.
        """
        stopping_criterion = self.stopping_criterion
        if stopping_criterion is None:
            raise ValueError(
                "Invalid stopping_criterion: None. Simulator.run needs a function of the simulator that "
                "returns True when the run should stop."
            )

        self.running = True
        self.initialize_logs()
        self.monitor()

        while self.running:
            print(f"Step {self.scheduler.steps + 1}")
            self.step()
            self.monitor()

            # Stopping once the criterion is met.
            if stopping_criterion(self):
                self.running = False

        self.dump_data()


# Naming the contract of an allocation algorithm: `Simulator.step` calls it once per ground station each
# tick, with the simulator and that station's parameters, and ignores what it returns.
AllocationAlgorithm = Callable[[Simulator, dict[str, Any]], object]


def find_component_class(class_name: str) -> type[ComponentManager]:
    """Returns the component class a scenario file names.

    Args:
        class_name (str): The class's `__name__`, as `save_scenary` wrote it.

    Returns:
        type: The component class.

    Raises:
        ValueError: If no component class has that name.
    """
    for component_class in ComponentManager.__subclasses__():
        if component_class.__name__ == class_name:
            return component_class

    known = sorted(component_class.__name__ for component_class in ComponentManager.__subclasses__())
    raise ValueError(f"Unknown component class: {class_name!r}. Expected one of {known}.")


def clear_components() -> None:
    """Empties the instance registry of every component class, so a new scenario starts from nothing.

    Simulators keep theirs: a simulator loads a scenario rather than being part of one.
    """
    for component_class in ComponentManager.__subclasses__():
        if component_class is not Simulator:
            component_class.clear_registry()
