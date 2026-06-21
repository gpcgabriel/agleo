# Simulator components
from ..component_manager import ComponentManager
from .network_link import NetworkLink
from .satellite import Satellite
from .user import User
from .application import Application
from .process_unit import ProcessUnit
from typing import List, Tuple, Optional, Dict, Any
from json import dump, dumps
import os
import traceback
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
            model=Ollama(id="llama3.2", host="http://localhost:11434", options={"temperature": 0}),
            tools=[self.apply_offloading_strategy],
            instructions=[
                "You are a Resource Management Controller for a LEO Satellite Network.",
                "You must choose ONE heuristic to run on the provided network state:",
                self.get_algorithms_descriptions(),
                "Call 'apply_offloading_strategy' with exactly 'best_fit_allocation' or 'longest_duration_allocation'.",
            ],
            markdown=True
        )

    def get_algorithms_descriptions(self):
        return """
**best_fit_allocation** — Minimizes resource fragmentation.
- For each pending app, finds the satellite ProcessUnit directly connected to user access points.
- If none available, falls back to ground station ProcessUnits reachable via terrestrial path.
- Picks the unit with smallest remaining capacity that still fits (tightest packing).
- Best when: CPU/memory/storage are scarce, many small apps pending, fragmentation is the main bottleneck.

**longest_duration_allocation** — Maximizes connection stability.
- Sorts pending apps by remaining required time (longest-duration apps allocated first).
- For satellite ProcessUnits: picks the one whose satellite has the longest future exposure time to the user (checks next N steps of orbital trace).
- For ground station ProcessUnits: picks first available with capacity and terrestrial path (infinite duration).
- Best when: satellite orbits are predictable (visible in 'future' coords), users have short satellite visibility windows, connection stability matters more than packing density.
"""

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

        scenario = parameters.get('scenario', 'hybrid')

        state = {
            "step": model.scheduler.steps,
            "scenario": scenario,
            "ground_station": GroundStation.export_groundstations().get(f"GS_{self.id}", {}),
            "satellites": Satellite.export_satellites(),
            "users": User.export_users(),
            "process_units": ProcessUnit.export_processunits(),
            "applications": Application.export_applications(),
            "topology": model.topology.export_topology(),
        }

        state_json = dumps(state, default=str)
        prompt_length = len(state_json)

        choice_criteria = (
            "Decision criteria:\n"
            "- If satellite future coords vary widely or users have short visibility windows (check topology.user_sat margin_pct), "
            "use 'longest_duration_allocation' to maximize connection duration.\n"
            "- If many apps compete for tight CPU/memory (check process_units cpu/mem surplus vs applications demands), "
            "use 'best_fit_allocation' to minimize fragmentation.\n"
            "- In 'terrestrial' scenario, prefer 'best_fit_allocation' (no satellite exposure windows exist).\n"
            "Call 'apply_offloading_strategy' with the best choice."
        )

        prompt = f"Network State (JSON):\n{state_json}\n\n{choice_criteria}"

        unprovisioned = sum(1 for a in Application.all() if not a.available)
        print(f"\n  [LLM] Step {model.scheduler.steps} | GS_{self.id} | "
              f"{unprovisioned} apps pending | "
              f"prompt ~{prompt_length} chars")

        try:
            response = self.offloading_agent.run(
                prompt,
                expected_output="The result of the tool call only."
            )

            response_dict = response.to_dict()
            tool_calls = response_dict.get("tool_calls") or response_dict.get("messages", [])
            chosen = "unknown"
            for item in tool_calls:
                if isinstance(item, dict) and item.get("function", {}).get("name") == "apply_offloading_strategy":
                    chosen = item["function"].get("arguments", {}).get("strategy_name", "unknown")
                    break

            print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | "
                  f"-> chosen: {chosen}")
        except Exception:
            traceback.print_exc()
            print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | "
                  f"-> FALLBACK to best_fit_allocation")
            from leosim.components.allocation_algorithms import best_fit_allocation
            best_fit_allocation(model, parameters)
            return

        output_data = {
            "step": model.scheduler.steps,
            "ground_station": self.id,
            "agent_response": response.to_dict(),
        }

        os.makedirs("logs", exist_ok=True)
        with open("logs/agent_log.jsonl", "a", encoding="utf-8") as f:
            f.write(dumps(output_data, default=str) + "\n")

    @staticmethod
    def export_groundstations() -> Dict:
        gs_data = {}
        for gs in GroundStation._instances:
            gpos = gs.coordinates
            gs_data[f"GS_{gs.id}"] = {
                "pos": (round(gpos[0], 1), round(gpos[1], 1)) if gpos else None,
                "range": gs.max_connection_range,
                "delay": gs.wireless_delay,
                "pus": [unit.id for unit in (gs.process_unit or [])],
                "users": [user.id for user in gs.users],
            }
        return gs_data