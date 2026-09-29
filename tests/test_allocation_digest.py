"""Tests for rendering the network state as a digest.

Two things are being protected. The digest has to carry every fact an
allocation strategy reads, since it replaced the serialized state entirely.
And it has to stay a translation: the moment it sorts, scores or omits a
candidate, the station agent stops deciding and starts rubber-stamping.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.allocation.digest import build_delay_by_satellite, render_digest, render_process_units


def make_state():
    """Builds a state shaped like `build_network_state` returns."""
    return {
        "step": 7,
        "scenario": "hybrid",
        "ground_station": {"pos": (-8.1, -34.9), "range": 1500},
        "satellites": {"Sat_4": {}, "Sat_9": {}},
        "process_units": {
            "PU_17": {"cpu_total": 30, "cpu_used": 26, "mem_total": 32, "mem_used": 12, "available": True},
            "PU_25": {"cpu_total": 41, "cpu_used": 0, "mem_total": 37, "mem_used": 0, "available": True},
        },
        "unit_hosts": {"PU_17": "Sat_4", "PU_25": "GS_1"},
        "applications": {
            "App_1": {"cpu": 20, "mem": 37, "remaining_time": 6, "provisioned_on": 24},
            "App_2": {"cpu": 10, "mem": 10, "remaining_time": 3, "provisioned_on": None},
        },
        "topology": {
            "link_count": 191,
            "gs_sat": [{"gs": 1, "sat": 4, "delay": 1.0432}, {"gs": 1, "sat": 9, "delay": 2.1}],
            "flows_active": 20,
            "flows_waiting": 0,
        },
    }


def test_every_reachable_unit_appears():
    """Omitting a candidate would be deciding, not translating."""
    lines = render_process_units(make_state()["process_units"], make_state()["unit_hosts"], {4: 1.0})

    assert len(lines) == 2


def test_units_keep_the_order_the_state_gave_them():
    """Sorting by fitness would hand the agent a ranking it did not ask for."""
    state = make_state()
    lines = render_process_units(state["process_units"], state["unit_hosts"], {4: 1.0})

    assert lines[0].split()[0] == "17"
    assert lines[1].split()[0] == "25"


def test_an_unavailable_unit_is_left_out():
    """Availability is a fact about the unit, not a judgement about its fit."""
    state = make_state()
    state["process_units"]["PU_17"]["available"] = False

    lines = render_process_units(state["process_units"], state["unit_hosts"], {})

    assert len(lines) == 1
    assert lines[0].split()[0] == "25"


def test_free_capacity_is_reported_instead_of_total_and_used():
    state = make_state()
    lines = render_process_units(state["process_units"], state["unit_hosts"], {4: 1.0})

    identifier, cpu_free, mem_free, host, delay = lines[0].split()
    assert (cpu_free, mem_free) == ("4", "20")


def test_a_unit_in_orbit_reports_its_satellite_and_link_delay():
    state = make_state()
    lines = render_process_units(state["process_units"], state["unit_hosts"], {4: 1.0})

    identifier, cpu_free, mem_free, host, delay = lines[0].split()
    assert host == "Sat_4"
    assert delay == "1.0"


def test_a_unit_on_the_station_reports_no_radio_hop():
    state = make_state()
    lines = render_process_units(state["process_units"], state["unit_hosts"], {4: 1.0})

    identifier, cpu_free, mem_free, host, delay = lines[1].split()
    assert host == "GS_1"
    assert delay == "0"


def test_a_unit_with_no_recorded_host_says_so_instead_of_guessing():
    state = make_state()
    state["unit_hosts"] = {}

    lines = render_process_units(state["process_units"], state["unit_hosts"], {4: 1.0})

    identifier, cpu_free, mem_free, host, delay = lines[0].split()
    assert host == "-"
    assert delay == "-"


def test_delays_are_rounded_so_the_digest_repeats_between_ticks():
    """A delay written to 16 decimals never repeats, and a cache over it never hits."""
    delays = build_delay_by_satellite(make_state()["topology"])

    assert delays == {4: 1.0, 9: 2.1}


def test_only_the_applications_this_station_was_asked_about_appear():
    digest = render_digest(make_state(), pending_app_ids=[1])

    assert "\n  1 20 37 6 24" in digest
    assert "\n  2 10 10 3" not in digest


def test_an_unplaced_application_says_so_instead_of_reporting_none():
    digest = render_digest(make_state(), pending_app_ids=[2])

    assert "\n  2 10 10 3 -" in digest


def test_the_digest_names_the_step_and_the_station():
    digest = render_digest(make_state(), pending_app_ids=[1])

    assert digest.startswith("STEP 7 | station at (-8.1, -34.9) | reach 1500 km | scenario hybrid")


def test_the_digest_is_far_shorter_than_the_serialized_state():
    """The whole reason it exists: elapsed time is linear in prompt length."""
    from json import dumps

    state = make_state()
    digest = render_digest(state, pending_app_ids=[1, 2])

    assert len(digest) < len(dumps(state, default=str)) / 2


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
