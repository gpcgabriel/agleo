"""The simulation session: sole owner of a running simulation's state."""

from leosim.components import GroundStation, Satellite, User

from app.core.bootstrap import build_simulator
from app.core.catalog import get_catalog
from app.core.snapshot import serialize_state


def create_session(config):
    """Builds a new simulation from a configuration.

    Args:
        config (SimulationConfig): Simulation parameters.

    Returns:
        SimulationSession: A session sitting at step zero.
    """
    simulator = build_simulator(config)
    return SimulationSession(simulator, config)


class SimulationSession:
    """Holds the simulator, the snapshot history and the viewing position."""

    def __init__(self, simulator, config):
        """Args:
            simulator (Simulator): An initialized simulator.
            config (SimulationConfig): The configuration it was built from.
        """
        self.simulator = simulator
        self.config = config
        self.catalog = get_catalog(config.satellites_path)

        self.history = []
        self.current_step_index = 0
        self.steps_remaining = 0

        # A freshly loaded scenario has not gone through a tick yet, so no
        # access point has connected its users. Without this, step 0 would be
        # drawn with every user disconnected, including those already in range.
        self.refresh_connectivity()
        self.commit_snapshot()

    # -- History ------------------------------------------------------------

    def commit_snapshot(self):
        """Captures the current state and makes it the viewed one.

        Returns:
            dict: The snapshot just created.
        """
        snapshot = serialize_state(self.simulator)
        snapshot["label"] = self._build_label(snapshot["step"])
        self.history.append(snapshot)
        self.current_step_index = len(self.history) - 1
        return snapshot

    def _build_label(self, step):
        """Names a snapshot after what it represents.

        The history holds two kinds of capture: the result of a tick, and the
        result of an infrastructure change, which does not advance the clock.
        The label keeps the two apart on the timeline.

        Args:
            step (int): Simulator tick at capture time.

        Returns:
            str: Label shown on the timeline.
        """
        changes_at_this_step = sum(1 for snapshot in self.history if snapshot["step"] == step)

        if changes_at_this_step == 0:
            return f"Step {step}"

        return f"Step {step} · change {changes_at_this_step}"

    def get_snapshot_labels(self):
        """Returns: list: Each snapshot's label, in history order."""
        return [snapshot["label"] for snapshot in self.history]

    def get_current_snapshot(self):
        """Returns: dict: The snapshot the operator is looking at."""
        return self.history[self.current_step_index]

    def get_latest_index(self):
        """Returns: int: Index of the most recent snapshot."""
        return len(self.history) - 1

    def get_step_count(self):
        """Returns: int: How many snapshots the history holds."""
        return len(self.history)

    def is_viewing_latest(self):
        """Returns: bool: True if the operator is on the most recent snapshot."""
        return self.current_step_index == self.get_latest_index()

    def view_step(self, index):
        """Moves the view to a point in the history.

        Args:
            index (int): Desired index.

        Raises:
            IndexError: If the index falls outside the history.
        """
        if not 0 <= index <= self.get_latest_index():
            raise IndexError(f"Step {index} is outside the history (0..{self.get_latest_index()}).")
        self.current_step_index = index

    # -- Advancing time -----------------------------------------------------

    def advance_one_step(self):
        """Advances the simulation by one tick and records the result.

        Returns:
            dict: The snapshot of the new step.
        """
        self.simulator.step()
        return self.commit_snapshot()

    def request_steps(self, steps):
        """Schedules a number of steps to run.

        Steps are consumed one at a time so the interface can draw progress
        and offer to interrupt between them.

        Args:
            steps (int): How many steps to run.
        """
        self.steps_remaining = max(0, int(steps))

    def has_pending_steps(self):
        """Returns: bool: True if scheduled steps remain."""
        return self.steps_remaining > 0

    def run_next_pending_step(self):
        """Runs one scheduled step.

        Returns:
            bool: True if this was the last scheduled step.
        """
        if not self.has_pending_steps():
            return True

        self.advance_one_step()
        self.steps_remaining -= 1
        return self.steps_remaining == 0

    def stop_stepping(self):
        """Discards scheduled steps that have not run yet."""
        self.steps_remaining = 0

    # -- Infrastructure changes ---------------------------------------------

    def refresh_connectivity(self):
        """Recomputes links and connections for the current positions.

        Runs the connectivity part of a tick without advancing the clock: it
        does not move satellites or users, does not accumulate time-based
        metrics and does not increment the step counter. This is what lets the
        operator see the effect of an infrastructure change right away.

        The order mirrors the scheduler's: connections are cleared, the
        topology is revised, and only then do access points reconnect the
        users within their range.
        """
        for user in User.all():
            user.network_access_points = []
        for satellite in Satellite.all():
            satellite.users = []
        for station in GroundStation.all():
            station.users = []

        topology = self.simulator.topology
        topology.remove_invalid_connections()
        self.simulator.topology_management_algorithm(
            topology=topology,
            **self.simulator.topology_management_parameters,
        )

        for satellite in Satellite.all():
            satellite.connect_users()

        for station in GroundStation.all():
            station.connection_to_satellites()
            station.connect_users()

        topology.update_delay()

    def apply_infrastructure_change(self):
        """Publishes a just-applied infrastructure change to the dashboard.

        Recomputes connectivity and records a new snapshot, so the operator
        sees the effect immediately without the simulation advancing in time.

        Returns:
            dict: The snapshot just created.
        """
        self.refresh_connectivity()
        return self.commit_snapshot()

    def __repr__(self):
        return (
            f"SimulationSession(step={self.simulator.scheduler.steps}, "
            f"snapshots={self.get_step_count()}, viewing={self.current_step_index}, "
            f"pending_steps={self.steps_remaining})"
        )
