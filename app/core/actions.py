"""Actions the agent can propose to the operator.

Each action has its own type and a payload with named, validated fields.
"""

from random import randint


class ActionType:
    """Identifiers of the supported actions.

    Plain string constants, so a proposal stays easy to inspect, log and
    serialize.
    """

    RUN_SIMULATION = "run_simulation"
    RESTART_SIMULATION = "restart_simulation"
    ADD_PROCESS_UNIT = "add_process_unit"
    ADD_NODES = "add_nodes"
    ADD_USER = "add_user"
    ADD_APP_TO_USER = "add_app_to_user"

    ALL = (
        RUN_SIMULATION,
        RESTART_SIMULATION,
        ADD_PROCESS_UNIT,
        ADD_NODES,
        ADD_USER,
        ADD_APP_TO_USER,
    )


def check_coordinates(lat, lon):
    """Validates a pair of geographic coordinates.

    Returns:
        tuple: (lat, lon) converted to float.

    Raises:
        ValueError: If latitude or longitude falls outside its valid range.
    """
    lat = float(lat)
    lon = float(lon)
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"Latitude outside the [-90, 90] range: {lat}.")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"Longitude outside the [-180, 180] range: {lon}.")
    return lat, lon


class RunSimulationPayload:
    """Data for advancing the simulation by N steps."""

    def __init__(self, steps):
        steps = int(steps)
        if steps < 1:
            raise ValueError(f"steps must be >= 1, got {steps}.")
        self.steps = steps

    def describe(self):
        """Returns: str: Human-readable description shown in the gate."""
        return f"Advance simulation by {self.steps} steps"


class RestartSimulationPayload:
    """Data for restarting the simulation at step zero."""

    def __init__(self, config):
        """Args: config (SimulationConfig): Resolved configuration of the restart."""
        self.config = config

    def describe(self):
        """Returns: str: Human-readable description shown in the gate."""
        return (
            f"Reset simulation to Step 0 "
            f"(scenario={self.config.scenario}, algorithm={self.config.algorithm}, "
            f"users={self.config.num_users}, satellites={self.config.num_satellites})"
        )


class AddProcessUnitPayload:
    """Data for attaching a process unit to an existing node."""

    TARGET_TYPES = ("Satellite", "GroundStation")

    def __init__(self, target_type, target_id, cpu, memory):
        if target_type not in self.TARGET_TYPES:
            raise ValueError(f"Invalid target_type: {target_type!r}. Expected one of {self.TARGET_TYPES}.")

        target_id = int(target_id)
        cpu = int(cpu)
        memory = int(memory)
        if cpu < 1:
            raise ValueError(f"cpu must be >= 1, got {cpu}.")
        if memory < 1:
            raise ValueError(f"memory must be >= 1, got {memory}.")

        self.target_type = target_type
        self.target_id = target_id
        self.cpu = cpu
        self.memory = memory

    def describe(self):
        """Returns: str: Human-readable description shown in the gate."""
        return f"Add ProcessUnit (CPU={self.cpu}, Mem={self.memory}) to {self.target_type} {self.target_id}"


class NodeSpec:
    """Description of a network node to create at a geographic position."""

    NODE_TYPES = ("Satellite", "GroundStation")

    # Altitude is a property of what the node is, not a choice the operator
    # makes. Satellites in the shipped traces sit between 320 and 528 km.
    DEFAULT_ALTITUDE = {"Satellite": 550.0, "GroundStation": 0.0}

    def __init__(self, node_type, lat, lon, alt=None, cpu=None, memory=None, defaulted=()):
        if node_type not in self.NODE_TYPES:
            raise ValueError(f"Invalid node_type: {node_type!r}. Expected one of {self.NODE_TYPES}.")

        lat, lon = check_coordinates(lat, lon)
        alt = self.DEFAULT_ALTITUDE[node_type] if alt is None else alt
        cpu = randint(20, 100) if cpu is None else int(cpu)
        memory = randint(20, 100) if memory is None else int(memory)
        if cpu < 1:
            raise ValueError(f"cpu must be >= 1, got {cpu}.")
        if memory < 1:
            raise ValueError(f"memory must be >= 1, got {memory}.")

        self.node_type = node_type
        self.lat = lat
        self.lon = lon
        self.alt = float(alt)
        self.cpu = cpu
        self.memory = memory
        # What the operator never stated, so the gate can say so.
        self.defaulted = tuple(sorted(defaulted))

    def describe(self):
        """Returns: str: Short description used when summarizing several nodes."""
        return (
            f"{self.node_type} at ({self.lat:.4f}, {self.lon:.4f}, {self.alt:.0f}km) "
            f"with CPU={self.cpu}, Mem={self.memory}"
        )


class AddNodesPayload:
    """Data for creating one or more new nodes in the topology."""

    def __init__(self, nodes):
        """Args: nodes (list): NodeSpec instances, at least one."""
        nodes = list(nodes)
        if not nodes:
            raise ValueError("The node list cannot be empty.")
        self.nodes = nodes

    def describe(self):
        """Returns: str: Human-readable description shown in the gate."""
        if len(self.nodes) == 1:
            return f"Add {self.nodes[0].describe()}"
        return f"Add {len(self.nodes)} nodes: " + ", ".join(node.describe() for node in self.nodes)

    def describe_defaults(self):
        """Returns: str: What was chosen for the operator, empty when nothing was.

        Kept apart from `describe` on purpose. The description is handed to the
        model as the tool's reply, and a note in brackets there comes back as an
        argument on the next call.
        """
        chosen = sorted({field for node in self.nodes for field in node.defaulted})
        if not chosen:
            return ""

        return f"Chosen automatically: {', '.join(chosen)}."


class AddUserPayload:
    """Data for creating a new user in the simulation."""

    def __init__(self, lat, lon, connection_range):
        lat, lon = check_coordinates(lat, lon)
        connection_range = int(connection_range)
        if connection_range < 1:
            raise ValueError(f"connection_range must be >= 1, got {connection_range}.")

        self.lat = lat
        self.lon = lon
        self.connection_range = connection_range

    def describe(self):
        """Returns: str: Human-readable description shown in the gate."""
        return f"Create user at ({self.lat:.4f}, {self.lon:.4f}) with range of {self.connection_range}km"


class AddAppToUserPayload:
    """Data for attaching an application to an existing user."""

    def __init__(self, user_id, cpu_demand, memory_demand):
        user_id = int(user_id)
        cpu_demand = int(cpu_demand)
        memory_demand = int(memory_demand)
        if cpu_demand < 1:
            raise ValueError(f"cpu_demand must be >= 1, got {cpu_demand}.")
        if memory_demand < 1:
            raise ValueError(f"memory_demand must be >= 1, got {memory_demand}.")

        self.user_id = user_id
        self.cpu_demand = cpu_demand
        self.memory_demand = memory_demand

    def describe(self):
        """Returns: str: Human-readable description shown in the gate."""
        return f"Create application (CPU={self.cpu_demand}, Mem={self.memory_demand}) " f"for User {self.user_id}"


class ProposedAction:
    """An action proposed by the agent, awaiting the operator's decision.

    A proposal does nothing by itself: it is only the typed record of what
    the agent asked for. The handler registered for its type executes it.
    """

    def __init__(self, action_type, payload):
        """Args:
            action_type (str): One of the ActionType constants.
            payload (object): The payload object matching that type.

        Raises:
            ValueError: If the type is not recognized.
        """
        if action_type not in ActionType.ALL:
            raise ValueError(f"Invalid action_type: {action_type!r}. Expected one of {ActionType.ALL}.")

        self.action_type = action_type
        self.payload = payload
        self.description = payload.describe()
        # Shown at the gate, never returned to the model.
        self.defaults_note = payload.describe_defaults() if hasattr(payload, "describe_defaults") else ""

    def __repr__(self):
        return f"ProposedAction(action_type={self.action_type!r}, description={self.description!r})"


# Actions a skill script can propose. All of them, including
# `restart_simulation`: the script names the settings to change and the runner
# resolves them against the configuration currently loaded, which only the
# dashboard's own process holds.
SCRIPTABLE_ACTIONS = ActionType.ALL

# Actions whose payload cannot be built where the script runs, so the script
# prints the arguments and the runner completes them.
ACTIONS_NEEDING_CURRENT_CONFIG = (ActionType.RESTART_SIMULATION,)


def build_payload(action_type, arguments, current_config=None):
    """Builds the payload for an action from plain arguments.

    Shared by the skill script, which validates before printing, and by the
    runner, which rebuilds the payload from what the script printed. Both
    boundaries therefore reject the same values.

    Args:
        action_type (str): One of `SCRIPTABLE_ACTIONS`.
        arguments (dict): Fields for that action.
        current_config (SimulationConfig): The configuration in use. Required
            by the actions in `ACTIONS_NEEDING_CURRENT_CONFIG` and ignored by
            the rest.

    Returns:
        object: The validated payload.

    Raises:
        ValueError: If the action is unknown or the arguments are invalid.
    """
    if action_type == ActionType.RESTART_SIMULATION:
        if current_config is None:
            raise ValueError("restart_simulation needs the configuration currently loaded.")
        return RestartSimulationPayload(current_config.copy_with(**arguments))

    if action_type == ActionType.RUN_SIMULATION:
        return RunSimulationPayload(arguments["steps"])

    if action_type == ActionType.ADD_PROCESS_UNIT:
        return AddProcessUnitPayload(
            arguments["target_type"], arguments["target_id"], arguments["cpu"], arguments["memory"]
        )

    if action_type == ActionType.ADD_USER:
        return AddUserPayload(arguments["lat"], arguments["lon"], arguments.get("connection_range", 1500))

    if action_type == ActionType.ADD_APP_TO_USER:
        return AddAppToUserPayload(arguments["user_id"], arguments["cpu"], arguments["memory"])

    if action_type == ActionType.ADD_NODES:
        return AddNodesPayload([NodeSpec(**spec) for spec in arguments["nodes"]])

    raise ValueError(f"Action {action_type!r} cannot be built from arguments. Expected one of {SCRIPTABLE_ACTIONS}.")
