# Importing the simulator components.
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..component_manager import ComponentManager
from .user import User

if TYPE_CHECKING:
    from .process_unit import ProcessUnit


# Naming the counter each migration stage adds its steps to.
MIGRATION_STAGE_TIMES = {
    "waiting": "waiting_time",
    "download_dependencies": "download_time",
    "application_state_migration": "application_state_migration_time",
}


class Application(ComponentManager):
    """Represents an application with specific resource demands.

    An Application is a unit of workload that can be requested by users,
    provisioned on processing units, and migrated between hosts during
    the simulation.

    Attributes:
        _instances (list): List of all created Application instances.
        _object_count (int): Counter for generating unique IDs.
        id (int): Unique identifier for the application.
        cpu_demand (int): CPU resource requirement.
        memory_demand (int): RAM resource requirement.
        storage_demand (int): Disk space resource requirement.
        dependency_labels (List[str]): Required software environment labels (e.g., 'docker').
        architectural_demands (dict): Specific hardware requirements (e.g., 'GPU').
        state (int): Current internal state/data size of the application.
        sla (int): Service Level Agreement threshold.
        user (object): Reference to the user who owns this application.
        process_unit (object): The host where the application is currently allocated.
        migrations (list): History of migration events and their status.
        available (bool): Whether the application is currently functional.
        being_provisioned (bool): Whether the application is in a setup/migration state.
        completed (bool): Whether the application lifecycle has ended.
    """

    _instances = []
    _object_count = 0

    def __init__(
        self,
        id: int = 0,
        cpu_demand: int = 0,
        memory_demand: int = 0,
        storage_demand: int = 0,
        dependency_labels: list[str] | None = None,
        architectural_demands: dict[str, Any] | None = None,
        state: int = 0,
        sla: int = 0,
    ) -> None:
        """Initializes an Application instance.

        Args:
            id (int): Unique ID. If 0, an ID is automatically assigned.
            cpu_demand (int, optional): CPU units required.
            memory_demand (int, optional): Memory units required.
            storage_demand (int, optional): Storage units required.
            dependency_labels (List[str]): List of software dependency tags.
            architectural_demands (dict): Specific hardware constraints.
            state (int):  State size.
            sla (int): SLA value.
        """
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        if id == 0:
            id = self.__class__._object_count
        self.id = id

        self.cpu_demand = cpu_demand
        self.memory_demand = memory_demand
        self.storage_demand = storage_demand
        self.state = state
        self.sla = sla
        self.dependency_labels = dependency_labels if dependency_labels is not None else []
        self.architectural_demands = architectural_demands if architectural_demands is not None else {}

        self.user: User | None = None
        self.process_unit = None
        self.migrations = []
        self.available = False
        self.available_when_stepped = False
        self.being_provisioned = False
        self.completed = False

    def collect_metrics(self) -> dict[str, Any]:
        """Collects telemetry data from this specific application instance.

        Returns:
            dict: A dictionary containing IDs, demands, current state,
                hosting information, and migration status.
        """
        last_migration = self.migrations[-1].copy() if self.migrations else None

        if last_migration:
            # Converting to string so the value can be written to disk.
            last_migration["origin"] = str(last_migration["origin"])
            last_migration["target"] = str(last_migration["target"])

        metrics = {
            "ID": self.id,
            "CPU Demand": self.cpu_demand,
            "Memory Demand": self.memory_demand,
            "Storage Demand": self.storage_demand,
            "State": self.state,
            "SLA": self.sla,
            "Process Unit": str(self.process_unit) if self.process_unit else None,
            "Available": self.available,
            "Being Provisioned": self.being_provisioned,
            "Last Migration": last_migration,
        }

        return metrics

    def step(self) -> None:
        """Updates the component state for the current simulation tick.

        Advances the migration under way, if any, and makes the application
        available exactly when its host is.
        """
        if self.migrations and self.migrations[-1]["end"] is None:
            self.advance_migration(self.migrations[-1])

        # Following the host: an application runs only on a unit that is available.
        self.available = bool(self.process_unit and self.process_unit.available)

        # Recording the availability this tick began with, which `User.collect_metrics` reports after
        # allocation and the process units may have changed `available`.
        self.available_when_stepped = self.available

    def advance_migration(self, migration: dict[str, Any]) -> None:
        """Moves a migration through its stages, logging the steps spent in each.

        Args:
            migration (dict): The migration under way, the last in `migrations`.
        """
        # TODO: Implement a formal dependency management system.
        # Standing in for the state machine until that system exists.
        dependencies_on_process_unit = []

        # Treating data transfer as instantaneous, which is what the model does today.
        if migration["status"] == "waiting" and (
            len(dependencies_on_process_unit) > 0 or len(dependencies_on_process_unit) == len(self.dependency_labels)
        ):
            migration["status"] = "download_dependencies"

        # Transitioning straight to the next stage while dependency simulation is
        # still pending.
        if migration["status"] == "download_dependencies" and len(dependencies_on_process_unit) == len(
            self.dependency_labels
        ):
            self.release_resources()
            # TODO: Implement complex state migration logic.
            stateless = self.process_unit is None or self.state == 0
            migration["status"] = "finished" if stateless else "application_state_migration"

        if migration["status"] == "finished":
            self.finish_migration(migration)
        elif migration["status"] in MIGRATION_STAGE_TIMES:
            migration[MIGRATION_STAGE_TIMES[migration["status"]]] += 1

    def release_resources(self) -> None:
        """Returns the CPU, memory and storage the application holds to its current unit, if it has one."""
        if self.process_unit:
            self.process_unit.cpu_demand -= self.cpu_demand
            self.process_unit.memory_demand -= self.memory_demand
            self.process_unit.storage_demand -= self.storage_demand

    def finish_migration(self, migration: dict[str, Any]) -> None:
        """Closes a migration and moves the application onto its target, available there.

        Args:
            migration (dict): The migration under way, the last in `migrations`.
        """
        migration["end"] = self.model.scheduler.steps + 1

        if self.process_unit:
            self.process_unit.applications.remove(self)

        target = migration["target"]
        self.process_unit = target
        target.applications.append(self)

        self.being_provisioned = False
        self.available = True

    def export(self) -> dict[str, Any]:
        """Generates a dictionary representation for context saving.

        Returns:
            dict: The serialized state of the application including
                relationships with users and processing units.
        """
        component = {
            "id": self.id,
            "cpu_demand": self.cpu_demand,
            "memory_demand": self.memory_demand,
            "storage_demand": self.storage_demand,
            "state": self.state,
            "sla": self.sla,
            "dependency_labels": self.dependency_labels,
            "architectural_demands": self.architectural_demands,
            "relationships": {
                "user": {"id": self.user.id, "class": type(self.user).__name__} if self.user else None,
                "process_unit": (
                    {"id": self.process_unit.id, "class": type(self.process_unit).__name__}
                    if self.process_unit
                    else None
                ),
            },
        }
        return component

    def provision(self, process_unit: ProcessUnit) -> None:
        """Starts the provisioning process on a target processing unit.

        Args:
            process_unit (object): The target host where the application
                will be provisioned.
        """
        if self.completed or self.being_provisioned:
            return

        self.being_provisioned = True

        # Reserving the resources on the target host immediately.
        process_unit.cpu_demand += self.cpu_demand
        process_unit.memory_demand += self.memory_demand
        process_unit.storage_demand += self.storage_demand

        self.migrations.append(
            {
                "status": "waiting",
                "origin": self.process_unit,
                "target": process_unit,
                "start": self.model.scheduler.steps + 1,
                "end": None,
                "waiting_time": 0,
                "download_time": 0,
                "application_state_migration_time": 0,
            }
        )

    def deprovision(self) -> None:
        """Ends the provisioning and releases resources from the current host.

        Resets availability and clears the reference to the processing unit.
        """
        self.available = False
        self.release_resources()

        if self.process_unit:
            self.process_unit.applications.remove(self)

        self.process_unit = None

    def access_status(self) -> tuple[bool, int]:
        """Reads whether the application is requested and how many steps its access still runs.

        The users are searched in order and each one's first access model of this
        application read, stopping at the first that requests it.

        Returns:
            tuple: (requested, remaining steps), the steps possibly negative.
        """
        pending = False
        remaining = 0

        for user in User.all():
            access_model = next(
                (
                    model
                    for model in user.applications_access_models
                    if model.application.id == self.id and model.history
                ),
                None,
            )
            if access_model is None:
                continue

            pending = access_model.request_provisioning
            last = access_model.history[-1]
            if last.get("required_provisioning_time"):
                remaining = last["required_provisioning_time"] - last["provisioned_time"]
            elif last.get("end"):
                remaining = last["end"] - self.model.scheduler.steps

            if pending:
                break

        return pending, remaining

    @staticmethod
    def export_applications() -> dict[str, dict[str, Any]]:
        apps = {}
        for app in Application.all():
            pending, remaining = app.access_status()
            apps[f"App_{app.id}"] = {
                "cpu": app.cpu_demand,
                "mem": app.memory_demand,
                "sto": app.storage_demand,
                "available": app.available,
                "pending": pending and not app.being_provisioned,
                "remaining_time": max(remaining, 0),
                "user": app.user.id if app.user else None,
                "provisioned_on": app.process_unit.id if app.process_unit else None,
            }
        return apps
