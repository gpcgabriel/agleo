# Importing the Python modules the manager relies on.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, ClassVar, Self

if TYPE_CHECKING:
    from .simulator import Simulator


class ComponentManager:
    # Holding the simulator every component belongs to; `Simulator.__init__` sets it on this class.
    model: ClassVar[Simulator]

    # Keeping each subclass's own registry, which `all` and `find_by` hand out typed as that subclass.
    _instances: ClassVar[list[Any]]
    _object_count: ClassVar[int]

    id: int
    # Holding the references a scenario file recorded for a loaded component, which
    # `Simulator.initialize` resolves into attributes.
    relationships: dict[str, Any]

    # Recording whether `save_scenary` writes this class's instances to the scenario file.
    saved_in_scenario = True

    def __str__(self) -> str:
        """Define an object representation
        Returns:
            obj (str): Object representation
        """
        return f"{self.__class__.__name__}_{self.id}"

    def __repr__(self) -> str:
        """Define an object representation
        Returns:
            str: Object representation.
        """
        return f"{self.__class__.__name__}_{self.id}"

    def export(self) -> dict[str, Any]:
        return {"id": self.id}

    def collect_metrics(self) -> dict[str, Any]:
        # Defining the object metrics collection.
        metrics: dict[str, Any] = {}

        return metrics

    @classmethod
    def collect_class_metrics(cls) -> list[dict[str, Any]]:
        # Collecting the metrics of every instance of the class.
        metrics: list[dict[str, Any]] = []

        for obj in cls.all():
            obj_metrics = obj.collect_metrics()

            if obj_metrics:
                metrics.append(obj_metrics)

        return metrics

    def set_attributes(self, **attributes: Any) -> None:
        # Setting an object's attributes from the values of a dictionary.
        for attribute_name, attribute_value in attributes.items():
            if attribute_name != "relationships":
                setattr(self, attribute_name, attribute_value)

    @classmethod
    def find_by(cls, attribute_name: str, value: object) -> Self | None:
        # Finding an object by the value of one of its attributes.
        obj = next((obj for obj in cls.all() if getattr(obj, attribute_name) == value), None)

        return obj

    @classmethod
    def all(cls) -> list[Self]:
        # Copying the list of instances so callers cannot mutate it.
        return cls._instances.copy()

    @classmethod
    def count(cls) -> int:
        return len(cls._instances)

    @classmethod
    def clear(cls) -> None:
        # Resetting the instance list and the object counter so a new scenario can
        # be loaded.
        cls._instances = []
        cls._object_count = 0

    @classmethod
    def remove(cls, obj: Self) -> None:
        # Removing an object from its class's instance list.
        if obj not in cls._instances:
            raise Exception(f"Object {obj} is not in the list of instances of the '{cls.__name__}' class.")

        cls._instances.remove(obj)

    @classmethod
    def save_scenary(
        cls, ignore_list: list[type[ComponentManager]] | None = None, filename: str = "dataset.json"
    ) -> dict[str, list[dict[str, Any]]]:
        # Exporting the context of the components of interest.
        scenary: dict[str, list[dict[str, Any]]] = {}

        for component_class in cls.__subclasses__():
            if component_class.saved_in_scenario and component_class not in (ignore_list or []):
                components: list[dict[str, Any]] = []

                for component in component_class.all():
                    component_context = component.export()

                    if component_context:
                        components.append(component_context)

                scenary[component_class.__name__] = components

        with open(filename, "w", encoding="UTF-8") as dataset:
            json.dump(scenary, dataset, indent=4)

        return scenary
