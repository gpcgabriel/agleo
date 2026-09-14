"""Configuration parameters of a simulation."""


class SimulationConfig:
    """Every parameter needed to build a simulation.

    Carried as a single object from the sidebar through simulator
    construction and restart proposals.
    """

    SCENARIOS = ("hybrid", "leo", "terrestrial")
    ALGORITHMS = ("best_fit_allocation", "longest_duration_allocation")

    def __init__(self, gml_path, satellites_path, num_users, num_satellites, scenario, algorithm):
        """Builds a simulation configuration.

        Args:
            gml_path (str): Path to the GML file with the terrestrial topology.
            satellites_path (str): Path to the JSON file with satellite traces.
            num_users (int): How many users to create.
            num_satellites (int): Maximum number of satellites to load.
            scenario (str): One of SimulationConfig.SCENARIOS.
            algorithm (str): One of SimulationConfig.ALGORITHMS.

        Raises:
            ValueError: If any parameter falls outside its expected domain.
        """
        if not gml_path:
            raise ValueError("gml_path is required.")
        if not satellites_path:
            raise ValueError("satellites_path is required.")

        num_users = int(num_users)
        if num_users < 1:
            raise ValueError(f"num_users must be >= 1, got {num_users}.")

        num_satellites = int(num_satellites)
        if num_satellites < 1:
            raise ValueError(f"num_satellites must be >= 1, got {num_satellites}.")

        if scenario not in self.SCENARIOS:
            raise ValueError(f"Invalid scenario: {scenario!r}. Expected one of {self.SCENARIOS}.")

        if algorithm not in self.ALGORITHMS:
            raise ValueError(f"Invalid algorithm: {algorithm!r}. Expected one of {self.ALGORITHMS}.")

        self.gml_path = gml_path
        self.satellites_path = satellites_path
        self.num_users = num_users
        self.num_satellites = num_satellites
        self.scenario = scenario
        self.algorithm = algorithm

    def copy_with(self, gml_path=None, satellites_path=None, num_users=None,
                  num_satellites=None, scenario=None, algorithm=None):
        """Returns a new configuration with only the given fields replaced.

        Fields left as None keep their current value. Used by restart
        proposals, where the operator usually changes one or two parameters.

        Returns:
            SimulationConfig: A new instance; this one is left unchanged.
        """
        return SimulationConfig(
            gml_path=gml_path if gml_path is not None else self.gml_path,
            satellites_path=satellites_path if satellites_path is not None else self.satellites_path,
            num_users=num_users if num_users is not None else self.num_users,
            num_satellites=num_satellites if num_satellites is not None else self.num_satellites,
            scenario=scenario if scenario is not None else self.scenario,
            algorithm=algorithm if algorithm is not None else self.algorithm,
        )

    def __repr__(self):
        return (
            f"SimulationConfig(gml_path={self.gml_path!r}, satellites_path={self.satellites_path!r}, "
            f"num_users={self.num_users}, num_satellites={self.num_satellites}, "
            f"scenario={self.scenario!r}, algorithm={self.algorithm!r})"
        )
