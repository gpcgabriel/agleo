"""LEOSim dashboard entry point.

Composition root: wires the interface layer to the domain, and owns nothing
of the simulation itself.
"""

import time

import streamlit as st

from app.core.actions import ActionType
from app.core.executor import execute_action
from app.ui.chat import render_chat_panel
from app.ui.css import inject_CSS
from app.ui.gui.styles import apply_theme, inject_accessibility_script
from app.ui.header import render_header
from app.ui.map import render_map
from app.ui.ollama import ollama_setup
from app.ui.session_init import session_init
from app.ui.sidebar import render_sidebar
from app.ui.state import (
    apply_result,
    clear_pending,
    consume_toast,
    get_pending,
    get_session,
    pending_is_confirmed,
    push_chat,
    queue_toast,
)

STEP_RENDER_DELAY_SECONDS = 0.5


def resolve_pending_action(session):
    """Runs the proposal the operator confirmed, if there is one.

    Args:
        session (SimulationSession): Active simulation.

    Returns:
        bool: True if something ran and the page should be reloaded.
    """
    if not pending_is_confirmed():
        return False

    action = get_pending()

    if action.action_type == ActionType.RUN_SIMULATION:
        spinner_message = f"⚙️ Running Network Simulation: {action.description}..."
    else:
        spinner_message = f"🔧 Applying physical network change: {action.description}..."

    with st.spinner(spinner_message):
        result = execute_action(session, action)

    apply_result(result)
    clear_pending()
    return True


def render_stepping_progress(session):
    """Draws the progress of scheduled steps and the stop button."""
    col_status, col_stop = st.columns([8, 4])

    with col_stop:
        st.markdown('<div class="btn-stop-marker"></div>', unsafe_allow_html=True)
        if st.button("Stop Simulation", use_container_width=True, key="stop_simulation_button"):
            session.stop_stepping()
            push_chat("system", "Simulation stopped by operator.")
            queue_toast("Simulation stopped!")
            st.rerun()

    with col_status:
        st.info(f"⚙️ Running Network Simulation... **{session.steps_remaining}** steps remaining.")


def advance_scheduled_steps(session):
    """Runs one scheduled step per render, keeping the interface responsive."""
    finished = session.run_next_pending_step()

    if finished:
        push_chat("system", "Step advancement completed successfully.")
        queue_toast("Simulation completed successfully!")
    else:
        render_stepping_progress(session)


def render_simulation(session, is_dark, agent_mode, ollama_ok):
    """Draws the two main columns: the map and the orchestrator."""
    col_map, col_chat = st.columns([7, 5])

    with col_map:
        render_map(session, is_dark)

    with col_chat:
        render_chat_panel(session, agent_mode, ollama_ok)


def main_app():
    """Runs the Streamlit app."""
    st.set_page_config(page_title="LEOSim Dashboard", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")

    session_init()

    is_dark = st.session_state["is_dark"]
    apply_theme(is_dark)

    ollama_ok = ollama_setup()
    sim_options = render_sidebar(ollama_ok)
    render_header(is_dark)

    session = get_session()

    if session is None:
        st.info("👈 Please configure and initialize the simulation in the sidebar to begin.")
    else:
        if resolve_pending_action(session):
            st.rerun()

        if session.has_pending_steps():
            advance_scheduled_steps(session)

        toast_message = consume_toast()
        if toast_message:
            st.toast(toast_message, icon="✅")

        if not session.has_pending_steps():
            render_simulation(session, is_dark, sim_options["agent_mode"], ollama_ok)

    inject_CSS(is_dark)

    # Accessibility (Axe-core compliance) helper script injection
    inject_accessibility_script(is_dark=is_dark)

    # Keep re-rendering while scheduled steps remain, so the operator sees
    # progress and can stop the run between steps.
    if session is not None and session.has_pending_steps():
        time.sleep(STEP_RENDER_DELAY_SECONDS)
        st.rerun()


if __name__ == "__main__":
    main_app()
