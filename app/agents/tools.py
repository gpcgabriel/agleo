"""Tools the dashboard agent uses to propose changes.

Each tool records a `ProposedAction` in the buffer and returns a short
sentence confirming the registration to the model. None of them applies the
change or knows anything about the interface: reading the buffer and deciding
what to do with the proposals is the UI layer's job.
"""

import json
from random import randint

from app.core.actions import (
    ActionType,
    AddAppToUserPayload,
    AddNodesPayload,
    AddProcessUnitPayload,
    AddUserPayload,
    NodeSpec,
    ProposedAction,
    RestartSimulationPayload,
    RunSimulationPayload,
)


COLLISION_OFFSET = 0.01


def _spread_out_collisions(specs, taken_positions):
    """Spreads apart nodes that would land on exactly the same position.

    Two nodes with identical coordinates overlap on the map and compete for
    the same links. Doing this in code keeps arithmetic out of the model's
    tool calls, where an unevaluated expression would be invalid JSON.

    Args:
        specs (list): Freshly built NodeSpec instances, in the requested order.
        taken_positions (set): (lat, lon) positions already occupied.

    Returns:
        list: The same nodes, with latitudes shifted where they collided.
    """
    adjusted = []

    for spec in specs:
        lat = spec.lat
        while (round(lat, 6), round(spec.lon, 6)) in taken_positions:
            lat += COLLISION_OFFSET

        taken_positions.add((round(lat, 6), round(spec.lon, 6)))

        if lat == spec.lat:
            adjusted.append(spec)
        else:
            adjusted.append(NodeSpec(spec.node_type, lat, spec.lon, spec.alt, spec.cpu, spec.memory))

    return adjusted


def _coerce_list(value, field_name):
    """Normalizes an argument that should have been a list.

    Local models often send arrays as JSON text (`"[1, 2]"`), or send a scalar
    when there is a single element. Both forms are accepted.

    Args:
        value: Value received from the model.
        field_name (str): Field name, used in the error message.

    Returns:
        list: The value normalized to a list.

    Raises:
        ValueError: If the received text is not valid JSON.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            raise ValueError(f"Could not read {field_name} as a list: {value!r}")

    if not isinstance(value, (list, tuple)):
        value = [value]

    return list(value)


class ProposalBuffer:
    """Collects the proposals produced during one agent run.

    An instance is created per agent call and discarded when it ends, so the
    proposals of one conversation never leak into another.
    """

    def __init__(self, current_config=None):
        """Args:
            current_config (SimulationConfig): Active simulation configuration,
                used as the base when the operator asks for a restart without
                specifying every parameter. May be None when no simulation has
                been loaded yet.
        """
        self.current_config = current_config
        self.proposals = []

    def get_proposals(self):
        """Returns: list: A copy of the recorded proposals, in creation order."""
        return list(self.proposals)

    def get_last_proposal(self):
        """Returns: ProposedAction or None: The most recent proposal."""
        if not self.proposals:
            return None
        return self.proposals[-1]

    def get_tools(self):
        """Returns: list: This instance's tools, ready to hand to the agent."""
        return [
            self.propose_run_simulation,
            self.propose_restart_simulation,
            self.propose_add_process_unit,
            self.propose_add_user,
            self.propose_add_app_to_user,
            self.propose_add_node,
        ]

    def _register(self, action):
        """Stores a proposal and builds the reply returned to the model.

        Returns:
            str: Confirmation message for the model.
        """
        self.proposals.append(action)
        return f"Proposal registered: {action.description}. Please confirm in the control panel."

    # -- Tools exposed to the agent -----------------------------------------

    def propose_run_simulation(self, steps: int) -> str:
        """Proposes to advance the simulation by a specific number of steps (ticks).

        Args:
            steps (int): Number of steps to advance.
        """
        try:
            payload = RunSimulationPayload(steps)
        except ValueError as error:
            return f"Error: {error}"

        return self._register(ProposedAction(ActionType.RUN_SIMULATION, payload))

    def propose_restart_simulation(
        self,
        selected_gml: str = None,
        selected_json: str = None,
        num_users: int = None,
        num_satellites: int = None,
        scenario: str = None,
        algorithm: str = None,
    ) -> str:
        """Proposes to restart the simulation back to the initial step (Step 0).

        Any argument left out keeps the value currently configured.

        Args:
            selected_gml (str, optional): Path to the terrestrial GML topology file.
            selected_json (str, optional): Path to the satellite traces JSON file.
            num_users (int, optional): Number of users.
            num_satellites (int, optional): Maximum number of satellites.
            scenario (str, optional): Scenario: "hybrid", "leo" or "terrestrial".
            algorithm (str, optional): Allocation algorithm.
        """
        if self.current_config is None:
            return "Error: there is no simulation loaded yet, so it cannot be restarted."

        try:
            config = self.current_config.copy_with(
                gml_path=selected_gml,
                satellites_path=selected_json,
                num_users=num_users,
                num_satellites=num_satellites,
                scenario=scenario,
                algorithm=algorithm,
            )
            payload = RestartSimulationPayload(config)
        except ValueError as error:
            return f"Error: {error}"

        return self._register(ProposedAction(ActionType.RESTART_SIMULATION, payload))

    def propose_add_process_unit(self, target_type: str, target_id: int, cpu: int, memory: int) -> str:
        """Proposes to add a new processing unit (ProcessUnit/Server) to an existing node.

        Args:
            target_type (str): Target node type: 'Satellite' or 'GroundStation'.
            target_id (int): The integer ID of the target. If the operator says
                             "GroundStation 1" or "Satellite 2", pass ONLY the
                             integer value (1 or 2).
            cpu (int): CPU capacity (for example 50 to 100).
            memory (int): Memory capacity (for example 50 to 100).
        """
        try:
            payload = AddProcessUnitPayload(target_type, target_id, cpu, memory)
        except (ValueError, TypeError) as error:
            return f"Error: {error}"

        return self._register(ProposedAction(ActionType.ADD_PROCESS_UNIT, payload))

    def propose_add_user(self, lat: float, lon: float, connection_range: int = 1500) -> str:
        """Proposes to create a new mobile user in the simulation.

        Args:
            lat (float): Initial user latitude.
            lon (float): Initial user longitude.
            connection_range (int): Maximum connection range in km.
        """
        try:
            payload = AddUserPayload(lat, lon, connection_range)
        except (ValueError, TypeError) as error:
            return f"Error: {error}"

        return self._register(ProposedAction(ActionType.ADD_USER, payload))

    def propose_add_app_to_user(self, user_id: int, cpu_demand: int, memory_demand: int) -> str:
        """Proposes to attach a new application with CPU and memory demands to a user.

        Args:
            user_id (int): ID of the target user.
            cpu_demand (int): CPU demand of the application.
            memory_demand (int): Memory demand of the application.
        """
        try:
            payload = AddAppToUserPayload(user_id, cpu_demand, memory_demand)
        except (ValueError, TypeError) as error:
            return f"Error: {error}"

        return self._register(ProposedAction(ActionType.ADD_APP_TO_USER, payload))

    def propose_add_node(self, node_types, latitudes, longitudes, altitudes) -> str:
        """Proposes to add one or more new nodes (Satellites or GroundStations).

        Args:
            node_types: List of node types, for example ["Satellite"].
            latitudes: List of latitudes, one per node.
            longitudes: List of longitudes, one per node.
            altitudes: List of altitudes, one per node.
        """
        try:
            node_types = _coerce_list(node_types, "node_types")
            latitudes = _coerce_list(latitudes, "latitudes")
            longitudes = _coerce_list(longitudes, "longitudes")
            altitudes = _coerce_list(altitudes, "altitudes")
        except ValueError as error:
            return f"Error: {error}"

        if not node_types:
            return "Error: no nodes provided."

        lengths = {len(node_types), len(latitudes), len(longitudes), len(altitudes)}
        if len(lengths) != 1:
            return (
                "Error: the parallel lists have different lengths "
                f"(node_types={len(node_types)}, latitudes={len(latitudes)}, "
                f"longitudes={len(longitudes)}, altitudes={len(altitudes)})."
            )

        specs = []
        for index in range(len(node_types)):
            try:
                specs.append(
                    NodeSpec(
                        node_type=node_types[index],
                        lat=latitudes[index],
                        lon=longitudes[index],
                        alt=altitudes[index],
                        cpu=randint(20, 100),
                        memory=randint(20, 100),
                    )
                )
            except (ValueError, TypeError) as error:
                return f"Error on node {index + 1}: {error}"

        # If the model splits one request across several calls, the nodes are
        # accumulated into a single proposal, so the operator confirms once.
        last = self.get_last_proposal()
        if last is not None and last.action_type == ActionType.ADD_NODES:
            taken = {(round(n.lat, 6), round(n.lon, 6)) for n in last.payload.nodes}
            merged = AddNodesPayload(last.payload.nodes + _spread_out_collisions(specs, taken))
            self.proposals[-1] = ProposedAction(ActionType.ADD_NODES, merged)
            return f"Proposal updated: {self.proposals[-1].description}. Please confirm in the control panel."

        return self._register(
            ProposedAction(ActionType.ADD_NODES, AddNodesPayload(_spread_out_collisions(specs, set())))
        )
