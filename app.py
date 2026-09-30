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
    agent_is_running,
    apply_result,
    clear_pending,
    consume_toast,
    get_pending,
    get_session,
    pending_is_confirmed,
    push_chat,
    queue_toast,
)

# How long one render is allowed to keep running steps. A step costs about
# 0.26 s and a render pass around 0.5 s on top, most of it the map: a budget
# of four steps keeps that overhead under a third of the wall clock while the
# Stop button stays within about a second of a click.
STEP_BATCH_SECONDS = 1.0

# Naming the progress strip so the stylesheets can tell it apart from an
# ordinary notice: it is the only live thing on the page while a batch runs.
PROGRESS_SLOT_KEY = "stepping_progress"


def controls_are_locked(session):
    """Tells whether the operator's controls have to be held this render.

    Args:
        session (SimulationSession or None): Active simulation, if any.

    Returns:
        bool: True while the agent is answering or steps are running.
    """
    if agent_is_running():
        return True

    return session is not None and session.has_pending_steps()


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
        if st.button("Stop Simulation", use_container_width=True, key="stop_simulation_button", type="primary"):
            session.stop_stepping()
            push_chat("system", "Simulation stopped by operator.")
            queue_toast("Simulation stopped!")
            st.rerun()

    with col_status:
        st.info(f"⚙️ Running Network Simulation... **{session.steps_remaining}** steps remaining.")


def advance_scheduled_steps(session, progress_slot):
    """Runs scheduled steps until this render's budget is spent.

    One step per render, followed by a half-second pause, spent two thirds of
    the wall clock waiting rather than simulating. Running a batch and drawing
    once removes the pause and most of the round trips.

    Args:
        session (SimulationSession): Active simulation.
        progress_slot: Container the progress strip is drawn into.

    Returns:
        bool: True if the batch emptied and the page should be redrawn.
    """
    # Drawing the strip before running anything. Streamlit sends each element as
    # it is created, so this is what the operator sees the instant they confirm;
    # drawing it afterwards left the page unchanged until the first batch had
    # already run.
    with progress_slot:
        render_stepping_progress(session)

    deadline = time.perf_counter() + STEP_BATCH_SECONDS

    finished = session.run_next_pending_step()
    while not finished and time.perf_counter() < deadline:
        finished = session.run_next_pending_step()

    if finished:
        push_chat("system", "Step advancement completed successfully.")
        queue_toast("Simulation completed successfully!")

    return finished


def render_simulation(session, is_dark, agent_mode, ollama_ok, locked):
    """Draws the two main columns: the map and the orchestrator.

    Args:
        session (SimulationSession): Active simulation.
        is_dark (bool): Whether the dark theme is on.
        agent_mode (str): The agent's action mode, or None if disabled.
        ollama_ok (bool): Whether Ollama is reachable.
        locked (bool): Whether the controls are held while work is in flight.
    """
    col_map, col_chat = st.columns([7, 5])

    with col_map:
        render_map(session, is_dark, locked)

    with col_chat:
        render_chat_panel(session, agent_mode, ollama_ok, locked)


def main_app():
    """Runs the Streamlit app."""
    st.set_page_config(page_title="LEOSim Dashboard", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")

    session_init()

    is_dark = st.session_state["is_dark"]
    apply_theme(is_dark)

    ollama_ok = ollama_setup()

    # Holding every control while the agent is answering or a batch of steps
    # is running. Streamlit stops the running script on any widget
    # interaction, and the sidebar and the confirmation gate stay clickable
    # through the whole run because the page is redrawn between batches.
    session = get_session()
    locked = controls_are_locked(session)

    sim_options = render_sidebar(ollama_ok, locked)
    render_header(is_dark, toggle_disabled=locked)

    # Every block below gets its place on the page before anything decides
    # whether to fill it. Streamlit addresses elements by their position in the
    # tree and appends at a new position instead of replacing what was there,
    # so a block that appears on only some renders — the spinner that runs a
    # confirmed action, the progress strip, a toast — pushes the dashboard down
    # a slot, and the previous render stays on the page with the fresh one
    # drawn underneath it.
    action_slot = st.container()
    progress_slot = st.container(key=PROGRESS_SLOT_KEY)
    notice_slot = st.container()
    dashboard_slot = st.container()

    just_finished = False

    if session is None:
        with dashboard_slot:
            st.info("👈 Please configure and initialize the simulation in the sidebar to begin.")
    else:
        with action_slot:
            if resolve_pending_action(session):
                st.rerun()

        if session.has_pending_steps():
            just_finished = advance_scheduled_steps(session, progress_slot)

        with notice_slot:
            toast_message = consume_toast()
            if toast_message:
                st.toast(toast_message, icon="✅")

        # Drawing the dashboard through the run as well. Skipping it left the
        # previous render's map and orchestrator on the page as a ghost: the
        # chat input is gone, so the rule that paints the orchestrator column
        # stops matching and everything in it flattens against the page, while
        # the chat avatars keep their own background and stay bright. Redrawing
        # costs about 175 ms per batch, measured, and the operator gets to
        # watch the network move, which is the point of stepping.
        with dashboard_slot:
            render_simulation(session, is_dark, sim_options["agent_mode"], ollama_ok, locked)

    inject_CSS(is_dark)

    # Injecting the accessibility helper script for axe-core compliance.
    inject_accessibility_script()

    # Re-rendering while scheduled steps remain, so the operator sees progress
    # and can stop the run between batches, and once more when the last batch
    # empties: that render drew its controls held, and they are free now.
    #
    # The reload is left until here rather than fired the moment the run ends,
    # because a slot that goes through one render with nothing in it keeps what
    # the previous render put there — Streamlit does not trim on the way to a
    # rerun — and the next render adds its own copy below.
    if session is not None and (session.has_pending_steps() or just_finished):
        st.rerun()


if __name__ == "__main__":
    main_app()
