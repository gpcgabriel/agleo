"""Tests for the allocation cost record.

The Phase 3 claim is a before/after comparison, so these assert the properties
that comparison depends on: every visit is counted exactly once, a reduction in
calls is never separated from the outcome it produced, and repeated writes do
not duplicate rows.
"""

import os
import sys
import tempfile
from json import loads

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.allocation.metrics import LOG_FILENAME, AllocationMetrics


def test_a_skipped_station_counts_as_skipped_not_as_a_call():
    metrics = AllocationMetrics()
    metrics.add_skip(0, 1, "no pending apps")

    row = metrics.summarize_by_step()[0]
    assert row["skipped"] == 1
    assert row["calls"] == 0


def test_an_answered_station_counts_as_one_call():
    metrics = AllocationMetrics()
    metrics.add_call(0, 1, "answered", 4, 2000, 1.5, 3, 1)

    row = metrics.summarize_by_step()[0]
    assert row["calls"] == 1
    assert row["skipped"] == 0
    assert row["fallbacks"] == 0


def test_a_fallback_is_a_call_and_is_marked_as_one():
    metrics = AllocationMetrics()
    metrics.add_call(0, 1, "fallback", 4, 2000, 0.2, 0, 0)

    row = metrics.summarize_by_step()[0]
    assert row["calls"] == 1
    assert row["fallbacks"] == 1


def test_a_step_carries_its_cost_next_to_its_outcome():
    metrics = AllocationMetrics()
    metrics.add_call(7, 1, "answered", 4, 2000, 1.5, 3, 1)
    metrics.add_call(7, 2, "answered", 6, 3000, 2.5, 2, 4)

    row = metrics.summarize_by_step()[0]
    assert row["step"] == 7
    assert row["calls"] == 2
    assert row["applications"] == 10
    assert row["prompt_chars"] == 5000
    assert row["elapsed_seconds"] == 4.0
    assert row["provisioned"] == 5
    assert row["failed"] == 5


def test_rows_come_back_in_step_order():
    metrics = AllocationMetrics()
    for step in (3, 1, 2):
        metrics.add_skip(step, 1, "no pending apps")

    assert [row["step"] for row in metrics.summarize_by_step()] == [1, 2, 3]


def test_prompt_tokens_are_reported_as_an_estimate():
    metrics = AllocationMetrics()
    metrics.add_call(0, 1, "answered", 4, 4000, 1.0, 1, 0)

    assert metrics.summarize_by_step()[0]["prompt_tokens_estimated"] == 1000


def test_writing_twice_does_not_duplicate_rows():
    """`allocate` writes after every station, so a rewrite must add nothing."""
    with tempfile.TemporaryDirectory() as directory:
        metrics = AllocationMetrics()
        metrics.add_call(0, 1, "answered", 4, 2000, 1.0, 1, 0)
        metrics.write(directory)
        metrics.write(directory)

        metrics.add_call(0, 2, "answered", 4, 2000, 1.0, 1, 0)
        metrics.write(directory)

        with open(os.path.join(directory, LOG_FILENAME), encoding="utf-8") as log_file:
            rows = [loads(line) for line in log_file if line.strip()]

        assert len(rows) == 2
        assert [row["ground_station"] for row in rows] == [1, 2]


def test_the_constructor_directory_wins_over_the_simulator_one():
    with tempfile.TemporaryDirectory() as chosen, tempfile.TemporaryDirectory() as ignored:
        metrics = AllocationMetrics(logs_directory=chosen)
        metrics.add_skip(0, 1, "no pending apps")
        metrics.write(ignored)

        assert os.path.exists(os.path.join(chosen, LOG_FILENAME))
        assert not os.path.exists(os.path.join(ignored, LOG_FILENAME))


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
