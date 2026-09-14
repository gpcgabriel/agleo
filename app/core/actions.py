"""Actions the agent can propose to the operator.

Each action has its own type and a payload with named, validated fields.
"""


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


def _check_coordinates(lat, lon):
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

    def __init__(self, node_type, lat, lon, alt, cpu, memory):
        if node_type not in self.NODE_TYPES:
            raise ValueError(f"Invalid node_type: {node_type!r}. Expected one of {self.NODE_TYPES}.")

        lat, lon = _check_coordinates(lat, lon)
        cpu = int(cpu)
        memory = int(memory)
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

    def describe(self):
        """Returns: str: Short description used when summarizing several nodes."""
        return f"{self.node_type} at ({self.lat:.4f}, {self.lon:.4f}) with CPU={self.cpu}, Mem={self.memory}"


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


class AddUserPayload:
    """Data for creating a new user in the simulation."""

    def __init__(self, lat, lon, connection_range):
        lat, lon = _check_coordinates(lat, lon)
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
        return (
            f"Create application (CPU={self.cpu_demand}, Mem={self.memory_demand}) "
            f"for User {self.user_id}"
        )


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

    def __repr__(self):
        return f"ProposedAction(action_type={self.action_type!r}, description={self.description!r})"
