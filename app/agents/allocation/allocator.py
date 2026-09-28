"""LLM-driven allocation strategy.

`LLMAllocator.allocate` has the same signature as the plain allocation
algorithms in `leosim`, so it is injected into the simulator the same way and
the engine stays free of the LLM stack.
"""

import logging
import os
import time
from json import dumps, loads

from agno.agent import Agent
from agno.models.ollama import Ollama
from leosim.components.allocation_algorithms import best_fit_allocation
from leosim.components.allocation_algorithms.hybrid_allocation import hybrid_allocation

from app.agents.allocation.decision import AllocationDecision, split_without_duplicates
from app.agents.allocation.metrics import AllocationMetrics
from app.agents.allocation.prompt import INSTRUCTIONS, build_allocation_prompt
from app.agents.allocation.state import collect_state

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_CONTEXT_SIZE = 8192
LOG_FILENAME = "agent_log.jsonl"


class LLMAllocator:
    """Decides, per ground station, which strategy places each application.

    One instance serves the whole simulation; it keeps the decision history of
    each station so the agent can see how its previous choices turned out.
    """

    def __init__(self, model_name=DEFAULT_MODEL, host=DEFAULT_HOST, logs_directory=None):
        """Args:
        model_name (str): Model identifier in Ollama.
        host (str): Ollama endpoint.
        logs_directory (str): Where to append the decision log. When None,
            the simulator's own logs directory is used.
        """
        self.model_name = model_name
        self.host = host
        self.logs_directory = logs_directory
        self.decisions_by_station = {}
        self.metrics = AllocationMetrics(logs_directory)

        self.agent = Agent(
            model=Ollama(
                id=model_name,
                host=host,
                options={"temperature": 0, "num_ctx": DEFAULT_CONTEXT_SIZE},
            ),
            instructions=INSTRUCTIONS,
            output_schema=AllocationDecision,
        )

    def get_decisions(self, station_id):
        """Returns: list: Past decisions recorded for a ground station."""
        return self.decisions_by_station.setdefault(station_id, [])

    def ask_model(self, prompt):
        """Asks the agent for a decision.

        The reply is constrained by the output schema, so it arrives already
        validated instead of being parsed out of free text.

        Args:
            prompt (str): The prompt to send.

        Returns:
            AllocationDecision: The model's decision.

        Raises:
            ValueError: If the reply does not match the schema.
        """
        response = self.agent.run(prompt)

        if not isinstance(response.content, AllocationDecision):
            raise ValueError(f"Model reply did not match the schema: {response.content!r}")

        return response.content

    def apply_decision(self, model, parameters, best_fit_ids, longest_duration_ids):
        """Places the applications according to a decision.

        Returns:
            dict: The allocation results.
        """
        return hybrid_allocation(model, parameters, best_fit_ids, longest_duration_ids, [], [])

    def record(self, model, station, best_fit_ids, longest_duration_ids, results):
        """Stores one decision and appends it to the log."""
        entry = {
            "step": model.scheduler.steps,
            "ground_station": station.id,
            "best_fit": best_fit_ids,
            "longest_duration": longest_duration_ids,
            "results": results,
        }
        self.get_decisions(station.id).append(entry)
        self.append_to_log(model, entry)

    def append_to_log(self, model, entry):
        """Appends one entry to the decision log, honouring the simulator's path."""
        directory = self.logs_directory or getattr(model, "logs_directory", "logs")
        os.makedirs(directory, exist_ok=True)

        with open(os.path.join(directory, LOG_FILENAME), "a", encoding="utf-8") as log_file:
            log_file.write(dumps(entry, default=str) + "\n")

    def allocate(self, model, parameters):
        """Allocation algorithm entry point.

        Args:
            model (Simulator): The running simulator.
            parameters (dict): Algorithm parameters, carrying the ground
                station under "ground_station".
        """
        station = parameters["ground_station"]
        scenario = parameters.get("scenario", "hybrid")

        step = model.scheduler.steps

        state, pending_app_ids, skip_reason = collect_state(model, station, scenario)
        if skip_reason:
            logger.debug("Step %s | GS_%s | skipped: %s", step, station.id, skip_reason)
            self.metrics.add_skip(step, station.id, skip_reason)
            self.metrics.write(getattr(model, "logs_directory", "logs"))
            return

        prompt = build_allocation_prompt(state, pending_app_ids, self.get_decisions(station.id))
        logger.debug(
            "Step %s | GS_%s | %s pending | prompt ~%s chars",
            model.scheduler.steps,
            station.id,
            len(pending_app_ids),
            len(prompt),
        )

        started = time.monotonic()
        try:
            decision = self.ask_model(prompt)
        except Exception:
            logger.exception(
                "Step %s | GS_%s | model failed, falling back to best_fit_allocation",
                step,
                station.id,
            )
            best_fit_allocation(model, parameters)
            self.append_to_log(model, {"step": step, "ground_station": station.id, "fallback": True})
            # `best_fit_allocation` returns nothing, so a fallback row carries no
            # allocation outcome. The "fallback" mark is what distinguishes it.
            self.metrics.add_call(
                step, station.id, "fallback", len(pending_app_ids), len(prompt), time.monotonic() - started, 0, 0
            )
            self.metrics.write(getattr(model, "logs_directory", "logs"))
            return

        elapsed = time.monotonic() - started

        best_fit_ids, longest_duration_ids = split_without_duplicates(decision)
        results = self.apply_decision(model, parameters, best_fit_ids, longest_duration_ids)

        if isinstance(results, str):
            results = loads(results)

        logger.info(
            "Step %s | GS_%s | provisioned=%s failed=%s",
            model.scheduler.steps,
            station.id,
            results.get("provisioned", 0),
            results.get("failed", 0),
        )
        self.record(model, station, best_fit_ids, longest_duration_ids, results)
        self.metrics.add_call(
            step,
            station.id,
            "answered",
            len(pending_app_ids),
            len(prompt),
            elapsed,
            results.get("provisioned", 0),
            results.get("failed", 0),
        )
        self.metrics.write(getattr(model, "logs_directory", "logs"))
