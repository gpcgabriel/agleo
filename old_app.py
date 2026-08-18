import streamlit as st
import folium
from streamlit_folium import st_folium
import glob
import os
import time

# Import modular styles, helper functions, and agent tools
from app.gui.styles import apply_theme, inject_accessibility_script
from app.helper_functions.slash_commands import get_help_message, SLASH_COMMANDS
from app.helper_functions.simulation_helper import (
    serialize_state,
    get_simulation_state_summary,
    initialize_simulation,
    execute_pending_action,
)

from app.dashboard_agent.run_agent import run_agent

# Import Ollama manager utilities
from app.helper_functions.ollama_helper import (
    is_ollama_running,
    start_ollama,
    list_local_models,
    pull_model,
    DEFAULT_MODEL,
)

# Import SVG icons
from app.gui.icons import (
    icon_satellite,
    icon_globe,
    icon_bot,
    icon_play,
    icon_stop,
    icon_check,
    icon_cancel,
    icon_users,
    icon_station,
    icon_chart,
    icon_sun,
    icon_moon,
    wrap_icon,
)

# Setup page layout
st.set_page_config(page_title="LEOSim Dashboard", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")

# Toast notification check (placed early so it fires on render)
if "toast_message" in st.session_state and st.session_state["toast_message"]:
    st.toast(st.session_state["toast_message"], icon="✅")
    del st.session_state["toast_message"]

# Initialize theme session state
if "is_dark" not in st.session_state:
    st.session_state["is_dark"] = True

# Read current theme state & apply CSS stylesheet
is_dark = st.session_state["is_dark"]
apply_theme(is_dark)

# Initialize session state variables
if "simulation_history" not in st.session_state:
    st.session_state["simulation_history"] = []
if "current_step_index" not in st.session_state:
    st.session_state["current_step_index"] = 0
if "pending_action" not in st.session_state:
    st.session_state["pending_action"] = None
if "chat_messages" not in st.session_state:
    st.session_state["chat_messages"] = [
        {
            "role": "assistant",
            "content": "Hello! I'm the LEOSim constellation control assistant. Enable the tools in the sidebar and use the chat to send me commands.",
        }
    ]
if "simulator" not in st.session_state:
    st.session_state["simulator"] = None
if "success_banner" not in st.session_state:
    st.session_state["success_banner"] = None
if "steps_remaining" not in st.session_state:
    st.session_state["steps_remaining"] = 0
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = DEFAULT_MODEL

# Ollama health check & auto-start / download prompt early in page rendering
ollama_ok = is_ollama_running()
if not ollama_ok:
    st.warning("Ollama is not running. The agent requires Ollama to function.")
    if st.button("Start Ollama", key="start_ollama_button"):
        with st.spinner("Starting Ollama daemon..."):
            if start_ollama():
                st.success("Ollama daemon started successfully!")
                st.rerun()
            else:
                st.error("Failed to start Ollama daemon. Please run 'ollama serve' in your terminal.")
else:
    # Verify if the default model is available
    local_models = list_local_models()
    default_downloaded = any(
        m == DEFAULT_MODEL or m.startswith(DEFAULT_MODEL + ":") or DEFAULT_MODEL.startswith(m + ":")
        for m in local_models
    )
    if not default_downloaded:
        st.info(f"Default model '{DEFAULT_MODEL}' is not available locally. Would you like to download it?")
        if st.button(f"Download {DEFAULT_MODEL}", key="download_default_model_button"):
            progress_placeholder = st.empty()

            def progress_cb(line):
                progress_placeholder.text(f"Ollama: {line}")

            with st.spinner("Downloading model... This may take a few minutes."):
                if pull_model(DEFAULT_MODEL, progress_callback=progress_cb):
                    st.success(f"Model '{DEFAULT_MODEL}' downloaded successfully!")
                    st.rerun()
                else:
                    st.error(
                        f"Failed to download model '{DEFAULT_MODEL}'. Please run 'ollama pull {DEFAULT_MODEL}' in terminal."
                    )

# Sidebar layout
st.sidebar.markdown(f"<h2>{wrap_icon(icon_satellite(22))} LEOSim Controller</h2>", unsafe_allow_html=True)

gml_options = glob.glob("datasets/*.gml")
json_options = [
    f
    for f in glob.glob("datasets/*.json")
    if "dataset" not in os.path.basename(f) and "temp" not in os.path.basename(f)
]

selected_gml = st.sidebar.selectbox("Terrestrial Topology (GML)", gml_options, key="selected_gml_key")
selected_json = st.sidebar.selectbox("Satellite Traces (JSON)", json_options, key="selected_json_key")

num_users = st.sidebar.number_input("Number of Users", min_value=1, max_value=1000, value=20, key="num_users_key")
num_satellites = st.sidebar.number_input(
    "Maximum Satellites", min_value=1, max_value=100, value=15, key="num_satellites_key"
)
scenario = st.sidebar.selectbox("Scenario", ["hybrid", "leo", "terrestrial"], key="scenario_key")
algorithm = st.sidebar.selectbox(
    "Allocation Algorithm", ["best_fit_allocation", "longest_duration_allocation"], key="algorithm_key"
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"## {wrap_icon(icon_bot(18))} Agent Settings", unsafe_allow_html=True)

# Model selector inside Agent Settings
if ollama_ok:
    local_models = list_local_models()
    if local_models:
        current_model = st.session_state.get("selected_model", DEFAULT_MODEL)
        default_index = 0
        for idx, m in enumerate(local_models):
            if m == current_model or m.startswith(current_model + ":") or current_model.startswith(m + ":"):
                default_index = idx
                break

        selected_model = st.sidebar.selectbox("LLM Model", local_models, index=default_index, key="model_selector_key")
        st.session_state["selected_model"] = selected_model
    else:
        st.sidebar.warning("No local models found.")
        st.session_state["selected_model"] = DEFAULT_MODEL
else:
    st.sidebar.error("Ollama is not running.")
    st.session_state["selected_model"] = DEFAULT_MODEL

# Checkbox to enable/disable agent actions
agent_actions_enabled = st.sidebar.checkbox("Allow Agent to execute actions", value=True)

if agent_actions_enabled:
    # Radio button to select agent mode (Tools or Skills)
    agent_mode = st.sidebar.radio("Agent Mode", ("Tools", "Skills"), key="agent_mode_key")
else:
    agent_mode = None

# Initialize Simulation button with CSS marker
st.sidebar.markdown('<div class="btn-initialize-marker"></div>', unsafe_allow_html=True)
if st.sidebar.button("Initialize Simulation", key="btn_initialize", use_container_width=True):
    with st.spinner("Initializing simulator..."):
        sim = initialize_simulation(selected_gml, selected_json, num_users, num_satellites, scenario, algorithm)
        st.session_state["simulator"] = sim
        initial_snapshot = serialize_state(sim)
        st.session_state["simulation_history"] = [initial_snapshot]
        st.session_state["current_step_index"] = 0
        st.session_state["pending_action"] = None
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "Simulation initialized successfully! The network is ready at initial state (Step 0).",
            }
        ]
        st.success("Simulation configured!")
        st.rerun()

# Check if simulation is initialized
if not st.session_state["simulation_history"]:
    st.info("👈 Please configure and initialize the simulation in the sidebar to begin.")
else:
    # Main Container Header (Title & Theme Toggle)
    col_title, col_toggle = st.columns([10, 2], vertical_alignment="center")
    with col_title:
        st.markdown(
            f"<h1>{wrap_icon(icon_satellite(26))} LEOSim - LEO Simulation Dashboard</h1>", unsafe_allow_html=True
        )
    with col_toggle:
        # Marker div so that sibling selector can target the button below
        st.markdown('<div class="theme-toggle-marker"></div>', unsafe_allow_html=True)
        btn_label = "☀️" if is_dark else "🌙"
        if st.button(btn_label, key="theme_toggle_btn", help="Toggle Light/Dark Theme"):
            st.session_state["is_dark"] = not is_dark
            st.rerun()

    # If there are steps remaining to run, run exactly one step here
    if st.session_state.get("steps_remaining", 0) > 0:
        sim = st.session_state["simulator"]
        sim.step()
        snapshot = serialize_state(sim)
        st.session_state["simulation_history"].append(snapshot)
        st.session_state["current_step_index"] = len(st.session_state["simulation_history"]) - 1
        st.session_state["steps_remaining"] -= 1

        if st.session_state["steps_remaining"] == 0:
            st.session_state["chat_messages"].append(
                {"role": "system", "content": "Step advancement completed successfully."}
            )
            st.session_state["toast_message"] = "Simulation completed successfully!"
            st.session_state["success_banner"] = "Simulation completed successfully!"

    # Render transient success banner
    if "success_banner" in st.session_state and st.session_state["success_banner"]:
        st.success(st.session_state["success_banner"], icon="✅")
        st.session_state["success_banner"] = None

    # Get active snapshot based on current step index
    history = st.session_state["simulation_history"]
    curr_idx = st.session_state["current_step_index"]
    snapshot = history[curr_idx]

    # Render steps remaining progress bar and stop button
    if st.session_state.get("steps_remaining", 0) > 0:
        col_status, col_stop = st.columns([8, 4])
        with col_status:
            st.info(f"⚙️ Running Network Simulation... **{st.session_state['steps_remaining']}** steps remaining.")
        with col_stop:
            st.markdown('<div class="btn-stop-marker"></div>', unsafe_allow_html=True)
            if st.button("Stop Simulation", use_container_width=True, key="stop_simulation_button"):
                st.session_state["steps_remaining"] = 0
                st.session_state["chat_messages"].append(
                    {"role": "system", "content": "Simulation stopped by operator."}
                )
                st.session_state["toast_message"] = "Simulation stopped!"
                st.session_state["success_banner"] = "Simulation stopped by operator."
                st.rerun()

    # 2 Column Layout
    col_map, col_chat = st.columns([7, 5])

    # Col 1: Map and Telemetry
    with col_map:
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
            st.info(
                "ℹ️ Simulation is at the initial step. Ask the Agent to advance steps in the chat to navigate history."
            )

        st.subheader(f"Status at Step: {snapshot['step']}")

        # Metrics Row
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("Active Satellites", len([s for s in snapshot["satellites"] if s["active"]]))
        m_col2.metric("Connected Users", len([u for u in snapshot["users"] if u["connected_aps"]]))
        m_col3.metric("Ground Stations", len(snapshot["ground_stations"]))
        m_col4.metric("Network Links", len(snapshot["links"]))

        # Map Construction
        map_center = [-15.669171, -48.013922]  # Default center (Brazil)

        # Create Folium Map with Dynamic Theme Aesthetics
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

            # Marker
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

    # Col 2: Chat Agent and Confirmation Gate
    with col_chat:
        st.markdown(f"<h3>{wrap_icon(icon_bot(20))} Agent Orchestrator</h3>", unsafe_allow_html=True)

        # Render Confirmation Gate
        pending = st.session_state["pending_action"]
        if pending:
            st.markdown(
                f"""<div class="proposed-box">
                <h4>{wrap_icon(icon_bot(20))} Agent Proposed Action</h4>
                <p style='margin: 5px 0;'><b>Change:</b> {pending['description']}</p>
                </div>""",
                unsafe_allow_html=True,
            )
            col_yes, col_no = st.columns(2)

            st.markdown('<div class="btn-confirm-marker"></div>', unsafe_allow_html=True)
            if col_yes.button("Confirm Execution", use_container_width=True, key="btn_confirm"):
                execute_pending_action()
                st.rerun()

            st.markdown('<div class="btn-cancel-marker"></div>', unsafe_allow_html=True)
            if col_no.button("Cancel Proposal", use_container_width=True, key="btn_cancel"):
                st.session_state["chat_messages"].append(
                    {"role": "system", "content": f"Action rejected by user: {pending['description']}"}
                )
                st.session_state["toast_message"] = f"Action cancelled: {pending['description']}"
                st.session_state["pending_action"] = None
                st.rerun()

        # Render Chat History
        chat_container = st.container(height=450)
        with chat_container:
            for msg in st.session_state["chat_messages"]:
                if msg["role"] == "system":
                    st.markdown(
                        f'<div class="system-msg">{wrap_icon(icon_bot(16))} {msg["content"]}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

        # --- DYNAMIC CHAT INPUT STATUS & PLACEHOLDER ---
        steps_active = st.session_state.get("steps_remaining", 0) > 0
        local_models = list_local_models() if ollama_ok else []
        selected_model = st.session_state.get("selected_model", DEFAULT_MODEL)

        # Check if the currently selected model is downloaded
        model_downloaded = (
            any(
                m == selected_model or m.startswith(selected_model + ":") or selected_model.startswith(m + ":")
                for m in local_models
            )
            if ollama_ok
            else False
        )

        # Set dynamic parameters for single chat_input widget
        if steps_active:
            placeholder = "⏳ Simulation in progress..."
            chat_disabled = True
        elif not ollama_ok:
            placeholder = "⚠️ Agent unavailable — Ollama not running"
            chat_disabled = True
        elif not model_downloaded:
            placeholder = f"⚠️ Agent unavailable — Model '{selected_model}' not downloaded"
            chat_disabled = True
        else:
            placeholder = "Type a command for the agent (e.g., 'Advance simulation by 3 steps')"
            chat_disabled = False

        if prompt := st.chat_input(placeholder, disabled=chat_disabled, key="agent_chat_input"):

            # Save and display the user's message immediately in the chat container
            st.session_state["chat_messages"].append({"role": "user", "content": prompt})

            with chat_container:
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Open assistant message space inside the chat container
                with st.chat_message("assistant"):
                    response_content = ""  # Variable to storage the final reponse

                    if prompt.lower().strip() in ("/", "/help"):
                        response_content = get_help_message()
                        st.markdown(response_content)

                    elif prompt.strip().startswith("/") and not any(
                        prompt.strip().startswith(c["cmd"].strip()) for c in SLASH_COMMANDS
                    ):
                        help_message = get_help_message()
                        response_content = f"**Unknown command:** `{prompt.strip()}`\n\n{help_message}"
                        st.markdown(response_content)

                    elif curr_idx != len(history) - 1:
                        response_content = "⚠️ You are viewing a historical step. To send commands, drag the slider to the most recent step."
                        st.error(response_content)

                    elif st.session_state["pending_action"] is not None:
                        response_content = "⚠️ Resolve the pending proposed action in the upper panel before continuing the conversation."
                        st.warning(response_content)

                    else:
                        # Instantiate the agent and run inference
                        with st.spinner("🤖 Agent calculating response (Inference)..."):

                            # Contextual state injection (Detailed state summary or minimal optimized summary)
                            if prompt.startswith("/") and not prompt.lower().startswith("/review"):
                                context_state = (
                                    "Quick Command Mode (Slash Command). "
                                    "Execute the corresponding action immediately by calling the appropriate tool."
                                )
                            else:
                                detailed_summary = get_simulation_state_summary(snapshot)
                                context_state = (
                                    "You have access to the current detailed simulation state below:\n\n"
                                    f"{detailed_summary}\n\n"
                                    "Use this data to answer informational questions. "
                                    "If the operator explicitly requests a change or advancement to the simulation in natural language, you MUST use the appropriate tool to propose the action."
                                )

                            selected_model = st.session_state.get("selected_model", DEFAULT_MODEL)

                            response = run_agent(prompt, selected_model, agent_mode, context_state)
                            response_content = response.content
                            st.markdown(response_content)

            # Save the generated response in the general history and reload the page
            st.session_state["chat_messages"].append({"role": "assistant", "content": response_content})
            st.rerun()

    # Format and escape all button SVGs for CSS url() injection
    play_svg = icon_play(16).replace("#", "%23")
    stop_svg = icon_stop(16).replace("#", "%23")
    check_svg = icon_check(16).replace("#", "%23")
    cancel_svg = icon_cancel(16).replace("#", "%23")
    sun_svg = icon_sun(18).replace("#", "%23")
    moon_svg = icon_moon(18).replace("#", "%23")

    toggle_svg_uri = sun_svg if is_dark else moon_svg

    st.markdown(
        f"""
    <style>
    /* Inject Initialize button icon */
    div[data-testid="element-container"]:has(.btn-initialize-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{play_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}
    
    /* Inject Stop button icon */
    div[data-testid="element-container"]:has(.btn-stop-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{stop_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}
    
    /* Inject Confirm button icon */
    div[data-testid="element-container"]:has(.btn-confirm-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{check_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}
    
    /* Inject Cancel button icon */
    div[data-testid="element-container"]:has(.btn-cancel-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{cancel_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}
    
    /* Inject Theme Toggle button icon */
    div[data-testid="element-container"]:has(.theme-toggle-marker) + div[data-testid="element-container"] button {{
        background-image: url("data:image/svg+xml;utf8,{toggle_svg_uri}") !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        color: transparent !important;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Accessibility (Axe-core compliance) helper script injection (triggers reload of gui/styles.py)
    inject_accessibility_script(is_dark=is_dark)

    # Rerun loop if simulation is running step-by-step
    if st.session_state.get("steps_remaining", 0) > 0:
        time.sleep(0.5)
        st.rerun()
