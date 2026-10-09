"""Rows of the telemetry tables, with the nested records written out as short labels.

A snapshot keeps an access point, a process unit or an application as a small
dictionary, which the agent's summary and the map read field by field. A table
cell cannot show a dictionary: Streamlit's grid prints it as `[object Object]`.
These rows replace each one with a label an operator can read at a glance, and
leave out a user's access points: a user in range of a dozen satellites made
that column wider than the rest of the table.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.snapshot import Snapshot


def describe_unit(unit: dict[str, Any]) -> str:
    """Returns: str: The process unit's id and capacities, as in "PU 5 · CPU 100 · Mem 100 · Sto 100"."""
    return f"PU {unit['id']} · CPU {unit['cpu']} · Mem {unit['memory']} · Sto {unit['storage']}"


def describe_application(application: dict[str, Any]) -> str:
    """Returns: str: The application's id, demands and where it runs, as in "App 4 · CPU 10 · Mem 20 · on PU 7"."""
    unit = application["allocated_to"]
    placement = f"on PU {unit}" if unit is not None else "not allocated"
    return (
        f"App {application['id']} · CPU {application['cpu_demand']} · Mem {application['memory_demand']} · {placement}"
    )


def satellite_rows(snapshot: Snapshot) -> list[dict[str, Any]]:
    """Returns: list: One row per satellite, its process unit written out."""
    return [
        {**satellite, "process_unit": describe_unit(satellite["process_unit"]) if satellite["process_unit"] else None}
        for satellite in snapshot["satellites"]
    ]


def ground_station_rows(snapshot: Snapshot) -> list[dict[str, Any]]:
    """Returns: list: One row per ground station, its process units written out."""
    return [
        {**station, "process_units": [describe_unit(unit) for unit in station["process_units"]]}
        for station in snapshot["ground_stations"]
    ]


def user_rows(snapshot: Snapshot) -> list[dict[str, Any]]:
    """Returns: list: One row per user, without its access points, its applications written out."""
    return [
        {
            **{column: value for column, value in user.items() if column != "connected_aps"},
            "applications": [describe_application(application) for application in user["applications"]],
        }
        for user in snapshot["users"]
    ]
