import glob
import os

import streamlit as st

from app.gui.icons import icon_bot, icon_satellite, wrap_icon
from app.helper_functions.ollama_helper import DEFAULT_MODEL, list_local_models
from app.helper_functions.simulation_helper import initialize_simulation, serialize_state


def render_sidebar(ollama_ok: bool) -> dict:
    """Render the sidebar: dataset pickers, simulation params, agent
    settings and the 'Initialize Simulation' action.

    Args:
        ollama_ok: whether Ollama is currently reachable (controls the
            model selector state).

    Returns:
        dict: current sidebar selections (dataset paths, sim params,
        whether agent actions are enabled, and the selected agent mode).
    """
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

            selected_model = st.sidebar.selectbox(
                "LLM Model", local_models, index=default_index, key="model_selector_key"
            )
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

    return {
        "selected_gml": selected_gml,
        "selected_json": selected_json,
        "num_users": num_users,
        "num_satellites": num_satellites,
        "scenario": scenario,
        "algorithm": algorithm,
        "agent_actions_enabled": agent_actions_enabled,
        "agent_mode": agent_mode,
    }
