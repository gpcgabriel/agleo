# Simulator components
from ..component_manager import ComponentManager
from .network_link import NetworkLink
from .satellite import Satellite
from .user import User
from typing import List, Tuple, Optional, Dict, Any
from json import dump
import os
from agno.agent import Agent
from agno.models.ollama import Ollama

class GroundStation(ComponentManager):
    """Represents a ground station providing wireless connectivity.

    Ground stations bridge the terrestrial network and the LEO (Low Earth Orbit) 
    satellite network. They provide connection points for both satellites 
    and terrestrial users. They are integrated into the simulation Topology 
    to manage link establishment.

    Attributes:
        _instances (list): List of all active GroundStation instances.
        _object_count (int): Counter for generating unique IDs.
        id (int): Unique identifier for the ground station.
        coordinates (tuple): Fixed geographical position (lat, lon, alt).
        wireless_delay (int): Inherent delay of the wireless interface.
        max_connection_range (int): Maximum distance for establishing a link.
        users (List[User]): List of users currently connected to this station.
    """

    _instances = []
    _object_count = 0
    
    def __init__(
        self,
        id: int = 0,
        coordinates: Optional[Tuple[float, float, float]] = None,
        wireless_delay: int = 0, 
        max_connection_range: int = 2000
    ) -> None:
        """Initializes a GroundStation instance.

        Args:
            id (int): Unique ID. If 0, it's automatically assigned.
            coordinates (tuple, optional): Fixed coordinates of the station.
            wireless_delay (int): Latency value for the wireless connection.
            max_connection_range (int): Range limit for wireless signals.
        """
        self.__class__._instances.append(self)
        self.__class__._object_count += 1
        
        if id == 0:
            id = self.__class__._object_count
        self.id = id
        
        # Ground station coordinates are stationary
        self.coordinates = coordinates
        
        # Values used for network link construction
        self.wireless_delay = wireless_delay
        self.max_connection_range = max_connection_range
        
        # Track currently associated users
        self.users: List[User] = []

        self.process_unit = []

        self.llm_params = None

        self.offloading_agent = Agent(
            model=Ollama(id="qwen3.5", options={"temperature": 0}),
            tools=[self.apply_offloading_strategy],
            instructions=[
                "You are an expert Resource Management Controller for a LEO Satellite Network.",
                "Below is the source code for the heuristics you can use. READ THEM to understand their logic:",
                self.get_algorithms_code(),
                "1. Analyze the current network state provided (CPU, load, visibility).",
                "2. Choose the best algorithm based on the source code logic provided above.",
                "3. Call 'apply_offloading_strategy' with the chosen strategy_name.",
            ],
            markdown=True
        )

    def get_algorithms_code(self):
        code_context = ""
        path = "leosim/components/allocation_algorithms"
        files = ["best_fit_allocation.py", "longest_duration_allocation.py"]
        
        for file in files:
            full_path = os.path.join(path, file)
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    code_context += f"\n--- SOURCE CODE FOR {file} ---\n{f.read()}\n"
        return code_context

    def apply_offloading_strategy(self, strategy_name: str) -> str:
        """
        Applies a resource allocation heuristic to the satellite network.
        Args:
            strategy_name (str): Name of the heuristic ('best_fit_allocation' or 'longest_duration_allocation').
        """
        from leosim.components.allocation_algorithms import best_fit_allocation, longest_duration_allocation

        algorithms = {
            "best_fit_allocation": best_fit_allocation,
            "longest_duration_allocation": longest_duration_allocation
        }

        model = ComponentManager.model
        if not model:
            return "Error: Simulator model not initialized."

        selected_heuristic = algorithms.get(strategy_name)
        if selected_heuristic:
            selected_heuristic(model, self.llm_params)
            return f"Successfully applied {strategy_name}."
        return f"Heuristic '{strategy_name}' not found."

    def export(self) -> Dict[str, Any]:
        """Generates a dictionary representation of the ground station state.

        Returns:
            dict: Serialized object data including user relationships 
                for persistence or logging.
        """
        component = {
            "id": self.id,
            "coordinates": self.coordinates,
            "wireless_delay": self.wireless_delay,
            "max_connection_range": self.max_connection_range,
            "relationships": {
                "users": [
                    {
                        "id": user.id,
                        "class": type(user).__name__
                    } for user in self.users
                ],
                "process_unit": [
                    {
                        "id": unit.id,
                        "class": type(unit).__name__
                    } for unit in self.process_unit
                ] if self.process_unit else None
            }
        }
        return component
    
    def connect_server(self, server) -> None:
        """Establishes a connection between the ground station and a server.

        Args:
            server: The server component to connect to.
        """
        self.process_unit.append(server)

        server.coordinates = self.coordinates

    def step(self) -> None:
        """Executes the ground station's logic for the current simulation tick.

        Manages satellite handovers and establishes connections with all 
        terrestrial users within range.
        """
        topology = self.model.topology
        
        # Handle orbital network connections
        self.connection_to_satellites()
          
        # Connect to all users within signal range
        self.users = []          
        for user in User.all():
            if topology.within_range(self, user):
                user.connect_to_access_point(self)

    def connection_to_satellites(self) -> None:
        """Establishes links with satellites acting as network gateways.

        Iterates through available satellites and creates a NetworkLink 
        if the satellite is within range and is configured as a gateway.
        """
        topology = self.model.topology
        
        for satellite in Satellite.all():
            if satellite.coordinates is None:
                # Skip if the satellite position is not currently updated
                continue
            
            # Check if satellite is within range and acts as a network access point
            if topology.within_range(self, satellite) and satellite.is_gateway:
                # Skip if the network link already exists
                if self.model.topology.has_edge(self, satellite):
                    continue
                
                # Instantiate and configure a new dynamic NetworkLink
                link = NetworkLink()
                
                link['topology'] = topology
                link['nodes'] = [satellite, self]
                link['bandwidth'] = NetworkLink.default_bandwidth
                link['delay'] = link.get_delay()
                link['type'] = 'dynamic'
                
                # Update the simulation topology with the new edge
                topology.add_edge(satellite, self)
                topology._adj[satellite][self] = link
                topology._adj[self][satellite] = link

    def resource_management_algorithm(self, model, parameters):
        parameters['ground_station'] = self
        self.llm_params = parameters

        current_state = f"""
        ### Current Simulation State
        - **Step**: {model.scheduler.steps}

        **Users:** {self.users}
        **Ground Station Coordinates:** {self.coordinates}
        **Ground Station Max Connection Range:** {self.max_connection_range} km
        **Ground Station Wireless Delay:** {self.wireless_delay} ms
        **Available Process Units for this Ground Station:** {self.process_unit}
        """

        response = self.offloading_agent.run(
            f"Current State:\n{current_state}\n\nApply the best heuristic.",
            expected_output="The result of the tool call only."
        )

        output_data = {
            "step": model.scheduler.steps,
            "agent_response": response.to_dict()
        }
        
        with open("logs/agent_log.json", "w", encoding="utf-8") as json_file:
            dump(output_data, json_file, indent=4)

        print(response.content)

    @staticmethod
    def export_groundstations() -> Dict:
        """Exports a summary of the ground station's current state (to LLM)."""
        grounds_data = {}
        for gs in GroundStation._instances:
            grounds_data[f'ID: {gs.id}'] = {
                "Coordinates": gs.coordinates,
                "Max Connection Range (km)": gs.max_connection_range,
                "Process Units Connected (IDs)": [unit.id for unit in (gs.process_unit or [])]
            }

        return grounds_data