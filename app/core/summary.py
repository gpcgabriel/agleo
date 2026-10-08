"""Textual summary of a snapshot, used as the agent's context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.core.snapshot import Snapshot


def summarize_snapshot(snapshot: Snapshot) -> str:
    """Formats the state snapshot into a markdown text summary for the AI agent context.

    Args:
        snapshot (dict): A snapshot from `app/core/snapshot.py`.

    Returns:
        str: One section each for the satellites, ground stations, users and links.
    """
    summary = [f"### Simulation State Information (Current Step: {snapshot['step']})"]

    summary.append("\n🛰️ Satellites in Constellation:")
    summary += summarize_satellites(snapshot["satellites"])

    summary.append("\n🏠 Ground Stations:")
    summary += summarize_ground_stations(snapshot["ground_stations"])

    summary.append("\n👥 Users & Application Demands:")
    summary += summarize_users(snapshot["users"])

    summary.append(f"\n🔗 Active Network Connections: {len(snapshot['links'])}")

    return "\n".join(summary)


def summarize_satellites(satellites: list[dict[str, Any]]) -> list[str]:
    """Returns: list: One line per active satellite, with the unit it carries."""
    active_sats = [s for s in satellites if s["active"]]
    if not active_sats:
        return ["  No active satellites at the moment."]

    lines = []
    for sat in active_sats:
        pu_info = "No CPU/Memory (no processing)"
        if sat["process_unit"]:
            pu = sat["process_unit"]
            pu_info = f"ProcessUnit {pu['id']} (CPU Capacity: {pu['cpu']}, Memory: {pu['memory']})"
        lines.append(f"  - {sat['name']} (ID: {sat['id']}): Lat/Lon: {sat['lat']:.4f}, {sat['lon']:.4f}. {pu_info}")
    return lines


def summarize_ground_stations(ground_stations: list[dict[str, Any]]) -> list[str]:
    """Returns: list: One line per ground station, with its servers."""
    if not ground_stations:
        return ["  No ground stations registered."]

    lines = []
    for gs in ground_stations:
        pu_details = [
            f"Server/ProcessUnit {pu['id']} (CPU: {pu['cpu']}, Mem: {pu['memory']})" for pu in gs["process_units"]
        ]
        pu_info = ", ".join(pu_details) if pu_details else "No processing unit (no server)"
        lines.append(f"  - GroundStation {gs['id']}: Lat/Lon: {gs['lat']:.4f}, {gs['lon']:.4f}. Servers: [{pu_info}]")
    return lines


def summarize_users(users: list[dict[str, Any]]) -> list[str]:
    """Returns: list: One line per user, with its connection and the allocation of each application."""
    if not users:
        return ["  No active users in the simulation."]

    lines = []
    for u in users:
        connected_aps_desc = [f"{ap['class']} {ap['id']}" for ap in u["connected_aps"]]
        conn_status = (
            f"Connected to: {', '.join(connected_aps_desc)}" if connected_aps_desc else "Disconnected (no signal)"
        )

        app_details = [describe_application(app) for app in u["applications"]]
        app_info = " | ".join(app_details) if app_details else "No active applications"

        lines.append(
            f"  - User ID {u['id']}: Lat/Lon: {u['lat']:.4f}, {u['lon']:.4f} | "
            f"Status: {conn_status} | Applications: {app_info}"
        )
    return lines


def describe_application(app: dict[str, Any]) -> str:
    """Returns: str: An application's demands and where it is allocated, if anywhere."""
    if app["allocated_to"] is not None:
        alloc = f"ALLOCATED/HOSTED on Server/ProcessUnit ID {app['allocated_to']}"
    else:
        alloc = "NOT ALLOCATED (waiting for resources)"
    return f"App ID {app['id']} [CPU Req: {app['cpu_demand']}, Mem Req: {app['memory_demand']} - Status: {alloc}]"
