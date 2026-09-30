"""Cost and outcome of each allocation round.

Phase 3 is about making an LLM tick affordable, and nothing can be claimed
about it without a record of what a tick costs today. This keeps that record
separate from `agent_log.jsonl`, which says what was *decided* rather than
what the decision cost.
"""

import os
from json import dumps

LOG_FILENAME = "allocation_metrics.jsonl"

# Rough conversion used only to put prompt sizes on a familiar scale. The
# exact count depends on the tokenizer, so it is reported as an estimate.
CHARS_PER_TOKEN = 4


class AllocationMetrics:
    """Collects one record per ground station visit.

    A visit either skips, answers, or falls back to the plain algorithm after
    the model failed. All three are recorded, because a reduction in calls is
    only meaningful next to the outcome it produced.
    """

    def __init__(self, logs_directory=None):
        """Args:
        logs_directory (str): Where to append the records. When None, the
            simulator's own logs directory is used at write time.
        """
        self.logs_directory = logs_directory
        self.records = []
        self.written = 0

    def add_skip(self, step, station_id, reason):
        """Records a station that was not asked at all.

        Args:
            step (int): Simulator tick.
            station_id (int): The ground station.
            reason (str): Why there was nothing to decide.
        """
        self.records.append(
            {
                "step": step,
                "ground_station": station_id,
                "outcome": "skipped",
                "reason": reason,
                "applications": 0,
                "prompt_chars": 0,
                "elapsed_seconds": 0.0,
                "provisioned": 0,
                "failed": 0,
                "omitted": 0,
                "invented": 0,
            }
        )

    def add_call(
        self,
        step,
        station_id,
        outcome,
        applications,
        prompt_chars,
        elapsed_seconds,
        provisioned,
        failed,
        omitted=0,
        invented=0,
    ):
        """Records a station that was asked.

        Args:
            step (int): Simulator tick.
            station_id (int): The ground station.
            outcome (str): "answered" or "fallback".
            applications (int): How many applications the question covered.
            prompt_chars (int): Length of the prompt sent.
            elapsed_seconds (float): Wall clock spent waiting for the model.
            provisioned (int): Applications placed.
            failed (int): Applications that could not be placed.
            omitted (int): Applications asked about that the reply left out.
                These are the decisions that used to leave no trace.
            invented (int): Ids the reply named that were never asked about.
        """
        self.records.append(
            {
                "step": step,
                "ground_station": station_id,
                "outcome": outcome,
                "reason": None,
                "applications": applications,
                "prompt_chars": prompt_chars,
                "elapsed_seconds": round(elapsed_seconds, 3),
                "provisioned": provisioned,
                "failed": failed,
                "omitted": omitted,
                "invented": invented,
            }
        )

    def summarize_by_step(self):
        """Aggregates the records into one row per tick.

        Returns:
            list: Rows ordered by step, each carrying the calls made, the
            stations skipped, prompt size, wall clock and allocation outcome.
        """
        by_step = {}
        for record in self.records:
            row = by_step.setdefault(
                record["step"],
                {
                    "step": record["step"],
                    "calls": 0,
                    "skipped": 0,
                    "fallbacks": 0,
                    "applications": 0,
                    "prompt_chars": 0,
                    "elapsed_seconds": 0.0,
                    "provisioned": 0,
                    "failed": 0,
                    "omitted": 0,
                    "invented": 0,
                },
            )
            if record["outcome"] == "skipped":
                row["skipped"] += 1
            else:
                row["calls"] += 1
                if record["outcome"] == "fallback":
                    row["fallbacks"] += 1

            row["applications"] += record["applications"]
            row["prompt_chars"] += record["prompt_chars"]
            row["elapsed_seconds"] += record["elapsed_seconds"]
            row["provisioned"] += record["provisioned"]
            row["failed"] += record["failed"]
            row["omitted"] += record.get("omitted", 0)
            row["invented"] += record.get("invented", 0)

        rows = [by_step[step] for step in sorted(by_step)]
        for row in rows:
            row["elapsed_seconds"] = round(row["elapsed_seconds"], 3)
            row["prompt_tokens_estimated"] = row["prompt_chars"] // CHARS_PER_TOKEN
        return rows

    def write(self, directory):
        """Appends the records added since the last write.

        Called after every station, so it must not rewrite what is already on
        disk; `written` is how many records the file already holds.

        Args:
            directory (str): Directory to write into, unless the constructor
                was given one.
        """
        pending = self.records[self.written :]
        if not pending:
            return

        target = self.logs_directory or directory
        os.makedirs(target, exist_ok=True)

        with open(os.path.join(target, LOG_FILENAME), "a", encoding="utf-8") as log_file:
            for record in pending:
                log_file.write(dumps(record, default=str) + "\n")

        self.written = len(self.records)
