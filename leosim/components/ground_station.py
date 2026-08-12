# Simulator components
from ..component_manager import ComponentManager
from .network_link import NetworkLink
from .satellite import Satellite
from .user import User
from .application import Application
from .process_unit import ProcessUnit
from typing import List, Tuple, Optional, Dict, Any
from json import dumps, loads
import os
import traceback
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
                "Objective: maximize provisioned apps. Choose a strategy per app from two options.",
                "",
                "best_fit: packs apps into the tightest-fitting PU, minimizing wasted resources.",
                "",
                "longest_duration: picks the satellite with the longest remaining visibility time for the user.",
                "",
                "Output ONLY a JSON object with two arrays of app IDs. No other text.",
                "Example: {\"best_fit\": [1, 2], \"longest_duration\": [3]}",
                "Each app ID must appear in exactly one array.",
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

        results = hybrid_allocation(
            model, self.llm_params,
            best_fit_apps, longest_duration_apps,
            [], []
        )

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

        all_apps = Application.export_applications()
        pending_app_ids = [
            int(k.split("_")[1]) for k, v in all_apps.items() if v.get("pending")
        ]
        if not pending_app_ids:
            print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | SKIP (no pending apps)")
            return

        has_reachable_satellite = False
        from geopy.distance import geodesic
        from math import sqrt
        for sat in Satellite.all():
            if sat.is_gateway and sat.active and sat.coordinates and self.coordinates:
                gd = geodesic(self.coordinates[:2], sat.coordinates[:2]).kilometers
                ad = (self.coordinates[2] - sat.coordinates[2]) / 1000
                dist = sqrt(gd ** 2 + ad ** 2)
                if dist < min(self.max_connection_range, sat.max_connection_range):
                    has_reachable_satellite = True
                    break
        if not has_reachable_satellite and not self.process_unit:
            print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | SKIP (no satellites/PUs in range)")
            return

        pending_set = set(pending_app_ids)

        all_users = User.export_users()
        relevant_users = {
            uid: uinfo for uid, uinfo in all_users.items()
            if any(aid in pending_set for aid in uinfo.get("pending_apps", []))
        }

        relevant_sat_ids = set()
        for uinfo in relevant_users.values():
            for ap in uinfo.get("access_points", []):
                if ap.startswith("Satellite_"):
                    relevant_sat_ids.add(int(ap.split("_")[1]))

        from geopy.distance import geodesic
        from math import sqrt
        for sat in Satellite.all():
            if sat.is_gateway and sat.active and sat.coordinates and self.coordinates:
                gd = geodesic(self.coordinates[:2], sat.coordinates[:2]).kilometers
                ad = (self.coordinates[2] - sat.coordinates[2]) / 1000
                dist = sqrt(gd ** 2 + ad ** 2)
                if dist < min(self.max_connection_range, sat.max_connection_range):
                    relevant_sat_ids.add(sat.id)

        all_sats = Satellite.export_satellites()
        trimmed_sats = {
            sid: sinfo for sid, sinfo in all_sats.items()
            if int(sid.split("_")[1]) in relevant_sat_ids
        }

        trimmed_pu_ids = set()
        for sinfo in trimmed_sats.values():
            pu = sinfo.get("pu")
            if pu:
                trimmed_pu_ids.add(pu["id"])
        for gs_pu in (self.process_unit or []):
            trimmed_pu_ids.add(gs_pu.id)

        for sinfo in trimmed_sats.values():
            sinfo.pop("range", None)
            sinfo.pop("gateway", None)
            sinfo.pop("pu", None)
            if "future" in sinfo:
                sinfo["future"] = sinfo["future"][:3]

        all_pus = ProcessUnit.export_processunits()
        trimmed_pus = {
            pid: pinfo for pid, pinfo in all_pus.items()
            if int(pid.split("_")[1]) in trimmed_pu_ids
        }

        trimmed_apps = {
            aid: ainfo for aid, ainfo in all_apps.items()
            if int(aid.split("_")[1]) in pending_set
        }

        trimmed_topology = model.topology.export_topology()
        trimmed_topology["user_sat"] = [
            link for link in trimmed_topology.get("user_sat", [])
            if link["user"] in {int(u.split("_")[1]) for u in relevant_users}
        ]
        trimmed_topology["gs_sat"] = [
            link for link in trimmed_topology.get("gs_sat", [])
            if link["gs"] == self.id
        ]

        state = {
            "step": model.scheduler.steps,
            "scenario": scenario,
            "ground_station": GroundStation.export_groundstations().get(f"GS_{self.id}", {}),
            "satellites": trimmed_sats,
            "users": relevant_users,
            "process_units": trimmed_pus,
            "applications": trimmed_apps,
            "topology": trimmed_topology,
        }

        state_json = dumps(state, default=str)
        prompt_length = len(state_json)

        pending_summary = f"PENDING APPS (IDs to allocate): {pending_app_ids}"

        history_context = ""
        if self.decision_history:
            history_context = "\n=== Past decisions (last 5 steps) ===\n"
            for h in self.decision_history[-5:]:
                r = h["results"]
                history_context += (
                    f"Step {h['step']}: "
                    f"bf={h['best_fit_apps']} ld={h['longest_duration_apps']} "
                    f"-> prov={r['provisioned']} fail={r['failed']}\n"
                )

        prompt = (
            f"{pending_summary}\nNetwork State (JSON):\n{state_json}\n\n{history_context}\n"
            "Respond ONLY with valid JSON (no markdown, no code fences, no extra text) in this exact format:\n"
            '{"best_fit": [list of app IDs as ints], "longest_duration": [list of app IDs as ints]}'
        )

        verbose = parameters.get("verbose", False)
        pending = sum(1 for a in state["applications"].values() if a.get("pending"))
        print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | {pending} pending | prompt ~{prompt_length} chars")

        if verbose:
            print(f"\n{'='*60}")
            print(f"  LLM PROMPT - Step {model.scheduler.steps} | GS_{self.id}")
            print(f"{'='*60}")
            print(f"  Scenario: {scenario}")
            print(f"  Pending apps: {pending_app_ids}")
            print(f"  Past decisions: {len(self.decision_history)} steps")

            print(f"\n  --- Satellites ---")
            for sid, sinfo in state["satellites"].items():
                pu = sinfo.get("pu")
                pu_str = f" | PU: cpu_free={pu['cpu_free']} mem_free={pu['mem_free']} sto_free={pu['sto_free']}" if pu else ""
                print(f"    {sid}: pos={sinfo['pos']} active={sinfo['active']}{pu_str}")

            print(f"\n  --- Process Units ---")
            for pid, pinfo in state["process_units"].items():
                print(f"    {pid}: cpu={pinfo['cpu_used']}/{pinfo['cpu_total']} "
                      f"mem={pinfo['mem_used']}/{pinfo['mem_total']} "
                      f"sto={pinfo['sto_used']}/{pinfo['sto_total']} "
                      f"apps={pinfo['apps']} available={pinfo['available']}")

            print(f"\n  --- Users & Apps ---")
            for uid, uinfo in state["users"].items():
                print(f"    {uid}: pos={uinfo['pos']} range={uinfo['range']} "
                      f"access_points={uinfo['access_points']} pending_apps={uinfo['pending_apps']}")

            print(f"\n  --- Full Prompt ---")
            print(prompt)
            print(f"\n{'='*60}")
            print(f"  END PROMPT")
            print(f"{'='*60}")

        try:
            response = self.offloading_agent.run(prompt, max_retries=1)
            content = response.content.strip()

            import re
            content = re.sub(r'^```(?:json)?\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)

            start = content.find('{')
            end = content.rfind('}')
            if start == -1 or end == -1 or end <= start:
                start = content.find('[')
                end = content.rfind(']')
            if start == -1 or end == -1 or end <= start:
                raise ValueError(f"No JSON found in response: {content[:200]}")

            json_str = content[start:end+1]

            try:
                parsed = loads(json_str)
            except Exception:
                import ast
                try:
                    json_str_single = re.sub(r"(?<!\\)'", '"', json_str)
                    json_str_single = re.sub(r',\s*\}', '}', json_str_single)
                    json_str_single = re.sub(r',\s*\]', ']', json_str_single)
                    parsed = loads(json_str_single)
                except Exception:
                    try:
                        parsed = ast.literal_eval(json_str)
                    except Exception as e2:
                        raise ValueError(f"Failed to parse LLM response: {e2} | raw block: {json_str[:300]}")

            best_fit_ids = parsed.get("best_fit", [])
            longest_dur_ids = parsed.get("longest_duration", [])

            seen = set(best_fit_ids)
            longest_dur_ids = [a for a in longest_dur_ids if a not in seen]

            allocation_result = self.allocate_apps(
                best_fit_ids, longest_dur_ids
            )

            try:
                input_tokens = response.metrics.get("input_tokens", 0) or response.metrics.get("prompt_tokens", 0) or 0
                output_tokens = response.metrics.get("output_tokens", 0) or response.metrics.get("completion_tokens", 0) or 0
            except Exception:
                input_tokens = len(state_json) // 4
                output_tokens = len(content) // 4

            parsed_result = loads(allocation_result) if isinstance(allocation_result, str) else {}
            print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | "
                  f"in: ~{input_tokens} tok | out: ~{output_tokens} tok | "
                  f"prov: {parsed_result.get('provisioned', 0)} "
                  f"fail: {parsed_result.get('failed', 0)}")

            if verbose:
                print(f"\n{'='*60}")
                print(f"  LLM RESPONSE - Step {model.scheduler.steps} | GS_{self.id}")
                print(f"{'='*60}")
                print(f"  Raw: {content}")
                print(f"  Parsed: best_fit={best_fit_ids}  longest_duration={longest_dur_ids}")
                print(f"  Result: {allocation_result}")
                print(f"{'='*60}\n")

            output_data = {
                "step": model.scheduler.steps,
                "ground_station": self.id,
                "best_fit": best_fit_ids,
                "longest_duration": longest_dur_ids,
                "result": allocation_result,
            }
        except Exception:
            traceback.print_exc()
            print(f"  [LLM] Step {model.scheduler.steps} | GS_{self.id} | FALLBACK to best_fit_allocation")
            if verbose:
                print(f"{'='*60}")
                print(f"  LLM FALLBACK - Step {model.scheduler.steps} | GS_{self.id}")
                print(f"{'='*60}")
                print(f"{'='*60}\n")
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