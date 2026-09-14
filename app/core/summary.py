"""Textual summary of a snapshot, used as the agent's context."""


def summarize_snapshot(snapshot):
    """
    Formats the state snapshot into a markdown text summary for the AI agent context.
    """
    summary = []
    summary.append(f"### Simulation State Information (Current Step: {snapshot['step']})")

    # Satellites summary
    summary.append("\n🛰️ Satellites in Constellation:")
    active_sats = [s for s in snapshot["satellites"] if s["active"]]
    if active_sats:
        for sat in active_sats:
            pu_info = "No CPU/Memory (no processing)"
            if sat["process_unit"]:
                pu = sat["process_unit"]
                pu_info = f"ProcessUnit {pu['id']} (CPU Capacity: {pu['cpu']}, Memory: {pu['memory']})"
            summary.append(
                f"  - {sat['name']} (ID: {sat['id']}): Lat/Lon: {sat['lat']:.4f}, {sat['lon']:.4f}. {pu_info}"
            )
    else:
        summary.append("  No active satellites at the moment.")

    # Ground Stations summary
    summary.append("\n🏠 Ground Stations:")
    if snapshot["ground_stations"]:
        for gs in snapshot["ground_stations"]:
            pu_details = []
            for pu in gs["process_units"]:
                pu_details.append(f"Server/ProcessUnit {pu['id']} (CPU: {pu['cpu']}, Mem: {pu['memory']})")
            pu_info = ", ".join(pu_details) if pu_details else "No processing unit (no server)"
            summary.append(
                f"  - GroundStation {gs['id']}: Lat/Lon: {gs['lat']:.4f}, {gs['lon']:.4f}. Servers: [{pu_info}]"
            )
    else:
        summary.append("  No ground stations registered.")

    # Users & Applications allocation summary
    summary.append("\n👥 Users & Application Demands:")
    if snapshot["users"]:
        for u in snapshot["users"]:
            connected_aps_desc = []
            for ap in u["connected_aps"]:
                connected_aps_desc.append(f"{ap['class']} {ap['id']}")
            conn_status = (
                f"Connected to: {', '.join(connected_aps_desc)}" if connected_aps_desc else "Disconnected (no signal)"
            )

            app_details = []
            for app in u["applications"]:
                if app["allocated_to"] is not None:
                    alloc = f"ALLOCATED/HOSTED on Server/ProcessUnit ID {app['allocated_to']}"
                else:
                    alloc = f"NOT ALLOCATED (waiting for resources)"
                app_details.append(
                    f"App ID {app['id']} [CPU Req: {app['cpu_demand']}, Mem Req: {app['memory_demand']} - Status: {alloc}]"
                )
            app_info = " | ".join(app_details) if app_details else "No active applications"

            summary.append(
                f"  - User ID {u['id']}: Lat/Lon: {u['lat']:.4f}, {u['lon']:.4f} | Status: {conn_status} | Applications: {app_info}"
            )
    else:
        summary.append("  No active users in the simulation.")

    # Links
    summary.append(f"\n🔗 Active Network Connections: {len(snapshot['links'])}")

    return "\n".join(summary)
