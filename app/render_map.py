import folium
import streamlit as st
from streamlit_folium import st_folium

from app.gui.icons import icon_globe, wrap_icon


def render_map(snapshot: dict, history: list, curr_idx: int, is_dark: bool) -> None:
    """Render the map/telemetry column: timeline slider, status metrics,
    the Folium map (links, ground stations, satellites, users) and the
    telemetry detail tabs.
    """
    st.markdown(f"<h3>{wrap_icon(icon_globe(20))} Network Visualization & Telemetry</h3>", unsafe_allow_html=True)

    # Timeline slider
    if len(history) > 1:
        slider_idx = st.slider(
            "Simulation Timeline (Scrub)",
            min_value=0,
            max_value=len(history) - 1,
            value=curr_idx,
            step=1,
            disabled=(st.session_state.get("steps_remaining", 0) > 0),
        )
        if slider_idx != curr_idx:
            st.session_state["current_step_index"] = slider_idx
            st.rerun()
    else:
        st.info("ℹ️ Simulation is at the initial step. Ask the Agent to advance steps in the chat to navigate history.")

    st.subheader(f"Status at Step: {snapshot['step']}")

    # Metrics Row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Active Satellites", len([s for s in snapshot["satellites"] if s["active"]]))
    m_col2.metric("Connected Users", len([u for u in snapshot["users"] if u["connected_aps"]]))
    m_col3.metric("Ground Stations", len(snapshot["ground_stations"]))
    m_col4.metric("Network Links", len(snapshot["links"]))

    # Map Construction
    map_center = [-15.669171, -48.013922]  # Default center (Brazil)

    tiles_theme = "CartoDB dark_matter" if is_dark else "CartoDB positron"
    dynamic_link_color = "#f59e0b" if is_dark else "#d97706"
    static_link_color = "#06b6d4" if is_dark else "#0284c7"

    m = folium.Map(location=map_center, zoom_start=4, tiles=tiles_theme, control_scale=True)

    # Render Connections/Links
    for link in snapshot["links"]:
        folium.PolyLine(
            locations=[
                [link["source"]["lat"], link["source"]["lon"]],
                [link["target"]["lat"], link["target"]["lon"]],
            ],
            color=dynamic_link_color if link["type"] == "dynamic" else static_link_color,
            weight=2,
            opacity=0.6,
            tooltip=f"Link {link['type']} | Delay: {link['delay']:.1f}ms | Bandwidth: {link['bandwidth']} Mbps",
        ).add_to(m)

    # Render Ground Stations
    for gs in snapshot["ground_stations"]:
        popup_html = f"<b>Ground Station {gs['id']}</b><br>Lat/Lon: {gs['lat']:.4f}, {gs['lon']:.4f}<br>Wireless Delay: {gs['wireless_delay']}ms<br>Server Capacity:"
        for pu in gs["process_units"]:
            popup_html += f"<br>- Server {pu['id']} (CPU: {pu['cpu']} | MEM: {pu['memory']})"

        folium.Marker(
            location=[gs["lat"], gs["lon"]],
            popup=popup_html,
            tooltip=f"Ground Station {gs['id']}",
            icon=folium.Icon(color="green", icon="home", prefix="fa"),
        ).add_to(m)

    # Render Satellites & Coverage Footprints
    for sat in snapshot["satellites"]:
        if not sat["active"]:
            continue

        popup_html = f"<b>{sat['name']} (ID: {sat['id']})</b><br>Lat/Lon: {sat['lat']:.4f}, {sat['lon']:.4f}<br>Alt: {sat['alt']:.1f}km<br>Gateway: {sat['is_gateway']}"
        if sat["process_unit"]:
            popup_html += f"<br>- Process Unit {sat['process_unit']['id']} (CPU: {sat['process_unit']['cpu']} | MEM: {sat['process_unit']['memory']})"

        # Circle for coverage footprint
        folium.Circle(
            location=[sat["lat"], sat["lon"]],
            radius=sat["max_connection_range"] * 1000,
            color="#0ea5e9",
            fill=True,
            fill_color="#0ea5e9",
            fill_opacity=0.08,
            weight=1,
        ).add_to(m)

        folium.Marker(
            location=[sat["lat"], sat["lon"]],
            popup=popup_html,
            tooltip=sat["name"],
            icon=folium.Icon(color="blue", icon="rocket", prefix="fa"),
        ).add_to(m)

    # Render Users
    for user in snapshot["users"]:
        popup_html = f"<b>User {user['id']}</b><br>Lat/Lon: {user['lat']:.4f}, {user['lon']:.4f}<br>Range: {user['max_connection_range']}km"
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

    # Render Map in Streamlit (Configured for standard viewports: 420px height ensures no scrollbar)
    MAP_HEIGHT = 420
    st_folium(m, width=None, height=MAP_HEIGHT, use_container_width=True, returned_objects=[], key="simulation_map")

    # Telemetry detail tab/expanders (Collapsed by default, English tabs)
    with st.expander("Telemetry Details", expanded=False):
        t_sat, t_gs, t_user = st.tabs(["Satellites", "Ground Stations", "Users"])
        with t_sat:
            st.dataframe(snapshot["satellites"])
        with t_gs:
            st.dataframe(snapshot["ground_stations"])
        with t_user:
            st.dataframe(snapshot["users"])
