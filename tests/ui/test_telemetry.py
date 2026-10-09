"""Tests for the rows of the telemetry tables.

Streamlit's grid prints a dictionary in a cell as `[object Object]`, so every
nested record of a snapshot has to reach the table as a label.
"""

from typing import Any

from app.core.config import SimulationConfig
from app.core.session import create_session
from app.ui.telemetry import ground_station_rows, satellite_rows, user_rows

UNIT = {"id": 5, "cpu": 100, "memory": 80, "storage": 60}


def make_snapshot() -> dict[str, Any]:
    """Returns: dict: A snapshot holding one of each record the tables write out."""
    return {
        "satellites": [
            {"id": 3, "active": True, "process_unit": UNIT},
            {"id": 4, "active": True, "process_unit": None},
        ],
        "ground_stations": [{"id": 11, "process_units": [UNIT]}],
        "users": [
            {
                "id": 1,
                "connected_aps": [{"id": 3, "class": "Satellite"}, {"id": 11, "class": "GroundStation"}],
                "applications": [
                    {"id": 7, "cpu_demand": 10, "memory_demand": 20, "storage_demand": 5, "allocated_to": 5},
                    {"id": 8, "cpu_demand": 1, "memory_demand": 2, "storage_demand": 3, "allocated_to": None},
                ],
            }
        ],
    }


def test_a_user_row_names_its_applications_and_leaves_out_its_access_points() -> None:
    row = user_rows(make_snapshot())[0]

    assert "connected_aps" not in row
    assert row["applications"] == ["App 7 · CPU 10 · Mem 20 · on PU 5", "App 8 · CPU 1 · Mem 2 · not allocated"]


def test_process_units_are_written_out_and_a_missing_one_stays_empty() -> None:
    satellites = satellite_rows(make_snapshot())

    assert [row["process_unit"] for row in satellites] == ["PU 5 · CPU 100 · Mem 80 · Sto 60", None]
    assert ground_station_rows(make_snapshot())[0]["process_units"] == ["PU 5 · CPU 100 · Mem 80 · Sto 60"]


def test_the_snapshot_itself_is_left_as_it_was() -> None:
    """The agent's summary and the map read the same records field by field."""
    snapshot = make_snapshot()

    user_rows(snapshot)
    satellite_rows(snapshot)

    assert snapshot["users"][0]["connected_aps"][0] == {"id": 3, "class": "Satellite"}
    assert snapshot["satellites"][0]["process_unit"] == UNIT


def test_no_cell_of_a_real_snapshot_holds_a_record() -> None:
    config = SimulationConfig(
        "datasets/rnp.gml", "datasets/satellites_brazil.json", 6, 6, "hybrid", "best_fit_allocation"
    )
    snapshot = create_session(config).get_current_snapshot()

    for rows in (satellite_rows(snapshot), ground_station_rows(snapshot), user_rows(snapshot)):
        for row in rows:
            for column, value in row.items():
                cells = value if isinstance(value, list) else [value]
                assert not any(isinstance(cell, dict) for cell in cells), f"{column} still holds a record: {value!r}"
