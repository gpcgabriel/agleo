"""Tests for the satellite traces catalog."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.catalog import SatelliteCatalog, get_catalog

TRACES = "datasets/satellites_brazil.json"
GROUND_STATION_3 = (-7.2306, -35.8811, 0)


def test_catalog_indexes_the_whole_file():
    catalog = get_catalog(TRACES)

    assert catalog.count_satellites() > 0
    assert catalog.count_positions() > catalog.count_satellites()
    assert catalog.step_count > 0


def test_closest_satellite_is_found_and_its_trace_starts_at_that_position():
    catalog = get_catalog(TRACES)
    catalog_id, position = catalog.get_closest_satellite(GROUND_STATION_3)

    assert catalog_id is not None
    trace = catalog.get_coordinates_trace(catalog_id, position)
    assert trace[0] == position
    assert len(trace) >= 1


def test_excluded_satellites_are_never_returned():
    catalog = get_catalog(TRACES)
    first_id, _ = catalog.get_closest_satellite(GROUND_STATION_3)
    second_id, _ = catalog.get_closest_satellite(GROUND_STATION_3, exclude_ids={first_id})

    assert second_id is not None
    assert second_id != first_id


def test_excluding_every_satellite_reports_no_candidate():
    catalog = get_catalog(TRACES)
    every_id = set(catalog.positions_by_id)

    assert catalog.get_closest_satellite(GROUND_STATION_3, exclude_ids=every_id) == (None, None)


def test_an_unknown_position_yields_a_single_point_trace():
    catalog = get_catalog(TRACES)
    assert catalog.get_coordinates_trace(999999999, (0.0, 0.0, 0.0)) == [(0.0, 0.0, 0.0)]


def test_lookup_is_fast_enough_for_interactive_use():
    """Adding a satellite happens while the operator waits, so the lookup has
    to stay well under a second over the full traces file."""
    catalog = get_catalog(TRACES)

    started = time.perf_counter()
    catalog.get_closest_satellite(GROUND_STATION_3)
    elapsed = time.perf_counter() - started

    assert elapsed < 1.0, f"lookup took {elapsed:.2f}s"


def test_the_same_file_is_indexed_only_once():
    assert get_catalog(TRACES) is get_catalog(TRACES)


def test_a_catalog_can_be_built_from_any_path():
    """The trace file chosen in the sidebar must reach the catalog."""
    catalog = SatelliteCatalog(TRACES)
    assert catalog.path == TRACES


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
