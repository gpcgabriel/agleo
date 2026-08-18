import streamlit as st
from app.helper_functions.simulation_helper import serialize_state
import time
from app.gui.styles import apply_theme, inject_accessibility_script
from app import render_map, render_sidebar, session_init, render_chat_panel, render_header, inject_CSS, ollama_setup


def main_app():
    """Main function to run the Streamlit app."""
    # Setup page layout
    st.set_page_config(page_title="LEOSim Dashboard", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")

    # Initialize session state
    session_init()

    # Read current theme state & apply CSS stylesheet
    is_dark = st.session_state["is_dark"]
    apply_theme(is_dark)

    # Check if Ollama is running and set up the environment
    ollama_ok = ollama_setup()

    # Render sidebar and header
    sim_options = render_sidebar(ollama_ok)
    render_header(is_dark)

    # Check if simulation is initialized and render the main content area accordingly
    if not st.session_state["simulation_history"]:
        st.info("👈 Please configure and initialize the simulation in the sidebar to begin.")
    else:
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
        if st.session_state["success_banner"]:
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

        if st.session_state.get("steps_remaining", 0) <= 0:
            # Render the main content area with map and chat panel
            col_map, col_chat = st.columns([7, 5])
            with col_map:
                render_map(
                    snapshot=st.session_state["simulation_history"][st.session_state["current_step_index"]],
                    curr_idx=st.session_state["current_step_index"],
                    history=st.session_state["simulation_history"],
                    is_dark=is_dark,
                )
            with col_chat:
                render_chat_panel(
                    curr_idx=st.session_state["current_step_index"],
                    history=st.session_state["simulation_history"],
                    snapshot=st.session_state["simulation_history"][st.session_state["current_step_index"]],
                    agent_mode=sim_options["agent_mode"],
                    ollama_ok=ollama_ok,
                )

    # inject CSS for styling
    inject_CSS(is_dark)

    # Accessibility (Axe-core compliance) helper script injection (triggers reload of gui/styles.py)
    inject_accessibility_script(is_dark=is_dark)

    # Rerun loop if simulation is running step-by-step
    if st.session_state.get("steps_remaining", 0) > 0:
        time.sleep(0.5)
        st.rerun()


if __name__ == "__main__":
    main_app()
