# Simulator components
from ..component_manager import ComponentManager
from .network_link import NetworkLink
from .satellite import Satellite
from .user import User
from .application import Application
from .process_unit import ProcessUnit
from typing import List, Tuple, Optional, Dict, Any
from json import dump, dumps, loads
import os
import re
import traceback
import re
from agno.agent import Agent
from agno.models.ollama import Ollama

class GroundStation(ComponentManager):

    _instances = []
    _object_count = 0

    def __init__(
        self,
        id: int = 0,
        coordinates: Optional[Tuple[float, float, float]] = None,
        wireless_delay: int = 0,
        max_connection_range: int = 2000
    ) -> None:
        self.__class__._instances.append(self)
        self.__class__._object_count += 1

        if id == 0:
            id = self.__class__._object_count
        self.id = id

        self.coordinates = coordinates
        self.wireless_delay = wireless_delay
        self.max_connection_range = max_connection_range

        self.users: List[User] = []
        self.process_unit = []
        self.llm_params = None

        self.decision_history = []

        self.offloading_agent = Agent(
            model=Ollama(id="llama3.1:8b", host="http://localhost:11434",
                         options={"temperature": 0, "num_ctx": 8192}),
            instructions=[
                "You allocate apps in a LEO satellite network.",
                "Objective: maximize provisioned apps. Split apps between two strategies.",
                "",
                "best_fit: packs apps into tightest-fitting PU. Good when CPU/mem is tight.",
                "",
                "longest_duration: picks satellite with longest visibility. Good when exposure time matters.",
                "",
                "Output ONLY a JSON object with two arrays of app IDs. No other text.",
                "Example: {\"best_fit\": [3, 6], \"longest_duration\": [5, 7]}",
                "For empty lists: {\"best_fit\": [], \"longest_duration\": [3, 6]}",
                "",
                "Guidelines:",
                "- In 'terrestrial' scenario: put all apps in best_fit.",
                "- Apps with remaining_time > 10: try longest_duration.",
                "- Satellites with short future coords: use longest_duration.",
                "- When many apps compete for few resources: best_fit.",
            ],
        )

    def export(self) -> Dict[str, Any]:
        component = {
            "id": self.id,
            "coordinates": self.coordinates,
            "wireless_delay": self.wireless_delay,
            "max_connection_range": self.max_connection_range,
            "relationships": {
                "users": [
                    {"id": user.id, "class": type(user).__name__}
                    for user in self.users
                ],
                "process_unit": [
                    {"id": unit.id, "class": type(unit).__name__}
                    for unit in self.process_unit
                ] if self.process_unit else None
            }
        }
        return component

    def allocate_apps(self, best_fit_apps: list, longest_duration_apps: list) -> str:
        from leosim.components.allocation_algorithms.hybrid_allocation import hybrid_allocation

        model = ComponentManager.model
        if not model:
            return "Error: Simulator model not initialized."

        results = hybrid_allocation(model, self.llm_params, best_fit_apps, longest_duration_apps)

        summary = f"Provisioned: {results['provisioned']}, Already: {results['already']}, Failed: {results['failed']}"
        print(f"  [LLM] GS_{self.id} | {summary}")

        self.decision_history.append({
            "step": model.scheduler.steps,
            "best_fit_apps": best_fit_apps,
            "longest_duration_apps": longest_duration_apps,
            "results": results,
        })

        return dumps(results, default=str)

    def connect_server(self, server) -> None:
        self.process_unit.append(server)
        server.coordinates = self.coordinates

    def step(self) -> None:
        topology = self.model.topology
        self.connection_to_satellites()
        self.users = []
        for user in User.all():
            if topology.within_range(self, user):
                user.connect_to_access_point(self)

    def connection_to_satellites(self) -> None:
        topology = self.model.topology
        for satellite in Satellite.all():
            if satellite.coordinates is None:
                continue
            if topology.within_range(self, satellite) and satellite.is_gateway:
                if self.model.topology.has_edge(self, satellite):
                    continue
                link = NetworkLink()
                link['topology'] = topology
                link['nodes'] = [satellite, self]
                link['bandwidth'] = NetworkLink.default_bandwidth
                link['delay'] = link.get_delay()
                link['type'] = 'dynamic'
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

        pending_app_ids = [
            int(k.split("_")[1]) for k, v in state["applications"].items() if v.get("pending")
        ]
        pending_summary = f"PENDING APPS (IDs to allocate): {pending_app_ids}"

        history_context = ""
        if self.decision_history:
            history_context = "\n=== Past decisions (last 5 steps) ===\n"
            for h in self.decision_history[-5:]:
                r = h["results"]
                history_context += (
                    f"Step {h['step']}: best_fit={h['best_fit_apps']} "
                    f"longest_dur={h['longest_duration_apps']} "
                    f"-> provisioned={r['provisioned']} failed={r['failed']}\n"
                )

        prompt = f"{pending_summary}\nNetwork State (JSON):\n{state_json}\n\n{history_context}\nOutput JSON allocation."

        pending = sum(1 for a in state["applications"].values() if a.get("pending"))
        print(f"\n  [LLM] Step {model.scheduler.steps} | GS_{self.id} | "
              f"{pending} apps pending | prompt ~{prompt_length} chars | "
              f"history: {len(self.decision_history)} steps")

        try:
            response = self.offloading_agent.run(prompt, max_retries=1)
            content = response.content.strip()

            json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
            if json_match:
                parsed = loads(json_match.group())
                best_fit_ids = parsed.get("best_fit", [])
                longest_dur_ids = parsed.get("longest_duration", [])
            else:
                raise ValueError(f"No JSON found in response: {content[:200]}")

            allocation_result = self.allocate_apps(best_fit_ids, longest_dur_ids)
            output_data = {
                "step": model.scheduler.steps,
                "ground_station": self.id,
                "best_fit": best_fit_ids,
                "longest": longest_dur_ids,
                "result": allocation_result,
            }
        except Exception:
            traceback.print_exc()
            print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | "
                  f"-> FALLBACK to best_fit_allocation")
            from leosim.components.allocation_algorithms import best_fit_allocation
            best_fit_allocation(model, parameters)
            output_data = {
                "step": model.scheduler.steps,
                "ground_station": self.id,
                "fallback": True,
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
