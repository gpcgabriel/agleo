"""The plan a whole simulation run is approved as."""


class SimulationPlan:
    """What to build, and for how long to run it.

    A plan is approved once and then runs to the end without a gate per step.
    What the operator consents to is therefore the plan rather than the
    sentence that produced it: a misread request is caught before the minutes
    are spent instead of after.
    """

    def __init__(self, config, steps):
        """Builds the plan of one run.

        Args:
            config (SimulationConfig): The simulation to build.
            steps (int): How many ticks to run.

        Raises:
            ValueError: If the step budget is not at least one.
        """
        steps = int(steps)
        if steps < 1:
            raise ValueError(f"steps must be >= 1, got {steps}.")

        self.config = config
        self.steps = steps

    def describe(self):
        """Returns: str: What the gate shows the operator before they approve."""
        return (
            f"Run a complete simulation of {self.steps} steps and report its metrics "
            f"(scenario={self.config.scenario}, algorithm={self.config.algorithm}, "
            f"users={self.config.num_users}, satellites={self.config.num_satellites})"
        )

    def __repr__(self):
        return f"SimulationPlan(steps={self.steps}, config={self.config!r})"
