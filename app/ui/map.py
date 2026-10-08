from __future__ import annotations

from typing import TYPE_CHECKING, Any

import folium
import streamlit as st
from streamlit_folium import st_folium

from app.ui.gui.icons import icon_globe, wrap_icon

if TYPE_CHECKING:
    from app.core.session import SimulationSession
    from app.core.snapshot import Snapshot

# Centring the map on Brazil, where the shipped topologies are.
MAP_CENTER = [-15.669171, -48.013922]
# Keeping standard viewports free of a scrollbar.
MAP_HEIGHT = 420


class MapColors:
    """The colors the map draws with in one theme."""

    def __init__(self, is_dark: bool) -> None:
        """Args:
        is_dark (bool): Whether the dark theme is on.
        """
        self.tiles = "CartoDB dark_matter" if is_dark else "CartoDB positron"
        # Matching the light theme's muted accents. The saturated sky blues that
        # were here read as glaring over the pale positron tiles.
        self.dynamic_link = "#f59e0b" if is_dark else "#b45309"
        self.static_link = "#06b6d4" if is_dark else "#1f6f8b"
        self.coverage = "#0ea5e9" if is_dark else "#1f6f8b"


def render_map(session: SimulationSession, is_dark: bool, locked: bool = False) -> None:
    """Render the map/telemetry column: timeline slider, status metrics,
    the Folium map (links, ground stations, satellites, users) and the
    telemetry detail tabs.

    Args:
        session (SimulationSession): Active simulation.
        is_dark (bool): Whether the dark theme is on.
        locked (bool): Whether the timeline is held while work is in flight.
    """
    snapshot = session.get_current_snapshot()
    st.markdown(f"<h3>{wrap_icon(icon_globe(20))} Network Visualization & Telemetry</h3>", unsafe_allow_html=True)

    render_timeline(session, locked)

    st.subheader(f"Status at {snapshot['label']}")
    render_status_metrics(snapshot)

    st_folium(
        build_map(snapshot, MapColors(is_dark)),
        width=None,
        height=MAP_HEIGHT,
        use_container_width=True,
        returned_objects=[],
        key="simulation_map",
    )

    # Rendering the telemetry detail expanders, collapsed by default.
    with st.expander("Telemetry Details", expanded=False):
        t_sat, t_gs, t_user = st.tabs(["Satellites", "Ground Stations", "Users"])
        with t_sat:
            st.dataframe(snapshot["satellites"])
        with t_gs:
            st.dataframe(snapshot["ground_stations"])
        with t_user:
            st.dataframe(snapshot["users"])


def render_timeline(session: SimulationSession, locked: bool) -> None:
    """Renders the slider that scrubs through the recorded snapshots, or a hint while there is only one.

    Args:
        session (SimulationSession): Active simulation.
        locked (bool): Whether the timeline is held while work is in flight.
    """
    if session.get_step_count() <= 1:
        st.info("ℹ️ Simulation is at the initial step. Ask the Agent to advance steps in the chat to navigate history.")
        return

    # Labelling the timeline slider with each snapshot's label rather than its
    # position: an infrastructure change does not advance the clock, so a
    # position number would read as a step number it does not correspond to.
    labels = session.get_snapshot_labels()
    slider_idx = st.select_slider(
        "Simulation Timeline (Scrub)",
        options=list(range(session.get_step_count())),
        value=session.current_step_index,
        format_func=labels.__getitem__,
        disabled=locked,
    )
    if slider_idx != session.current_step_index:
        session.view_step(slider_idx)
        st.rerun()


def render_status_metrics(snapshot: Snapshot) -> None:
    """Renders the row of counts: active satellites, connected users, ground stations and links."""
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Active Satellites", len([s for s in snapshot["satellites"] if s["active"]]))
    m_col2.metric("Connected Users", len([u for u in snapshot["users"] if u["connected_aps"]]))
    m_col3.metric("Ground Stations", len(snapshot["ground_stations"]))
    m_col4.metric("Network Links", len(snapshot["links"]))


def build_map(snapshot: Snapshot, colors: MapColors) -> folium.Map:
    """Returns: folium.Map: The links, ground stations, active satellites and users of a snapshot, drawn in order."""
    m = folium.Map(location=MAP_CENTER, zoom_start=4, tiles=colors.tiles, control_scale=True)

    for link in snapshot["links"]:
        add_link(m, link, colors)

    for gs in snapshot["ground_stations"]:
        add_ground_station(m, gs)

    for sat in snapshot["satellites"]:
        if sat["active"]:
            add_satellite(m, sat, colors)

    for user in snapshot["users"]:
        add_user(m, user)

    return m


def add_link(m: folium.Map, link: dict[str, Any], colors: MapColors) -> None:
    """Draws a link as a line, colored by whether it is dynamic."""
    folium.PolyLine(
        locations=[
            [link["source"]["lat"], link["source"]["lon"]],
            [link["target"]["lat"], link["target"]["lon"]],
        ],
        color=colors.dynamic_link if link["type"] == "dynamic" else colors.static_link,
        weight=2,
        opacity=0.6,
        tooltip=f"Link {link['type']} | Delay: {link['delay']:.1f}ms | Bandwidth: {link['bandwidth']} Mbps",
    ).add_to(m)


def add_ground_station(m: folium.Map, gs: dict[str, Any]) -> None:
    """Draws a ground station as a marker whose popup lists its servers."""
    popup_html = (
        f"<b>Ground Station {gs['id']}</b><br>Lat/Lon: {gs['lat']:.4f}, {gs['lon']:.4f}"
        f"<br>Wireless Delay: {gs['wireless_delay']}ms<br>Server Capacity:"
    )
    for pu in gs["process_units"]:
        popup_html += f"<br>- Server {pu['id']} (CPU: {pu['cpu']} | MEM: {pu['memory']})"

    folium.Marker(
        location=[gs["lat"], gs["lon"]],
        popup=popup_html,
        tooltip=f"Ground Station {gs['id']}",
        icon=folium.Icon(color="green", icon="home", prefix="fa"),
    ).add_to(m)


def add_satellite(m: folium.Map, sat: dict[str, Any], colors: MapColors) -> None:
    """Draws a satellite as a marker over the circle of its coverage footprint."""
    popup_html = (
        f"<b>{sat['name']} (ID: {sat['id']})</b><br>Lat/Lon: {sat['lat']:.4f}, {sat['lon']:.4f}"
        f"<br>Alt: {sat['alt']:.1f}km<br>Gateway: {sat['is_gateway']}"
    )
    if sat["process_unit"]:
        unit = sat["process_unit"]
        popup_html += f"<br>- Process Unit {unit['id']} (CPU: {unit['cpu']} | MEM: {unit['memory']})"

    folium.Circle(
        location=[sat["lat"], sat["lon"]],
        radius=sat["max_connection_range"] * 1000,
        color=colors.coverage,
        fill=True,
        fill_color=colors.coverage,
        fill_opacity=0.08,
        weight=1,
    ).add_to(m)

    folium.Marker(
        location=[sat["lat"], sat["lon"]],
        popup=popup_html,
        tooltip=sat["name"],
        icon=folium.Icon(color="blue", icon="rocket", prefix="fa"),
    ).add_to(m)


def add_user(m: folium.Map, user: dict[str, Any]) -> None:
    """Draws a user as a marker whose popup lists its access points and applications."""
    popup_html = (
        f"<b>User {user['id']}</b><br>Lat/Lon: {user['lat']:.4f}, {user['lon']:.4f}"
        f"<br>Range: {user['max_connection_range']}km"
    )
    if user["connected_aps"]:
        ap_list = ", ".join([f"{ap['class']} {ap['id']}" for ap in user["connected_aps"]])
        popup_html += f"<br>Connected APs: {ap_list}"
    else:
        popup_html += "<br>Status: Disconnected"

    for app in user["applications"]:
        popup_html += f"<br>- App {app['id']} (CPU Req: {app['cpu_demand']} | Alloc: {app['allocated_to']})"

    folium.Marker(
        location=[user["lat"], user["lon"]],
        popup=popup_html,
        tooltip=f"User {user['id']}",
        icon=folium.Icon(color="red", icon="user", prefix="fa"),
    ).add_to(m)
