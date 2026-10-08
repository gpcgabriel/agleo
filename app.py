"""LEOSim dashboard entry point.

Composition root: wires the interface layer to the domain, and owns nothing
of the simulation itself.
"""

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from app.core.actions import ActionType
from app.core.executor import execute_action
from app.core.report import collect_run_metrics, summarize_run
from app.core.session import SimulationSession
from app.ui.chat import answer_pending_prompt, render_chat_panel, take_gate_decision, take_submitted_prompt
from app.ui.css import inject_css
from app.ui.gui.styles import apply_theme, inject_page_scripts
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

# Naming the progress strip so the stylesheets can tell it apart from an
# ordinary notice: it is the only live thing on the page while steps run.
PROGRESS_SLOT_KEY = "stepping_progress"


def controls_are_locked(session: SimulationSession | None) -> bool:
    """Tells whether the operator's controls have to be held this render.

    Args:
        session (SimulationSession or None): Active simulation, if any.

    Returns:
        bool: True while the agent is answering or steps are running.
    """
    if agent_is_running():
        return True

    return session is not None and session.has_pending_steps()


def resolve_pending_action(session: SimulationSession) -> bool:
    """Runs the proposal the operator confirmed, if there is one.

    Args:
        session (SimulationSession): Active simulation.

    Returns:
        bool: True if something ran and the page should be reloaded.
    """
    action = get_pending()
    if action is None or not pending_is_confirmed():
        return False

    if action.action_type in (ActionType.RUN_SIMULATION, ActionType.RUN_FULL_SIMULATION):
        spinner_message = f"⚙️ Running Network Simulation: {action.description}..."
    else:
        spinner_message = f"🔧 Applying physical network change: {action.description}..."

    with st.spinner(spinner_message):
        result = execute_action(session, action)

    apply_result(result)
    clear_pending()
    return True


def render_stepping_progress(session: SimulationSession) -> None:
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


def run_scheduled_step(session: SimulationSession) -> None:
    """Runs one scheduled step, after the page shows the step before it.

    One step per render, so the map and the counter show every step of a run;
    running steps for a second per render drew only every fourth. The step runs
    once the page is drawn, so the operator sees the state it starts from while
    it runs, and the Stop button answers within one step.

    Args:
        session (SimulationSession): Active simulation.
    """
    finished = session.run_next_pending_step()

    # Saying nothing when a plan is finishing: `report_finished_plan` answers
    # that run with its metrics, and a bare "completed successfully" above the
    # report would be the same news twice.
    if finished and session.active_plan is None:
        push_chat("system", "Step advancement completed successfully.")
        queue_toast("Simulation completed successfully!")


def report_finished_plan(session: SimulationSession) -> bool:
    """Writes the report of a plan whose run has just ended.

    A plan is approved once and then runs unattended, so the metrics are the
    whole answer: the operator was not watching the ticks go by. This covers a
    run the operator stopped early too, which reports over what did run.

    Args:
        session (SimulationSession): Active simulation.

    Returns:
        bool: True if a report was written.
    """
    plan = session.take_finished_plan()
    if plan is None:
        return False

    push_chat("assistant", summarize_run(plan, collect_run_metrics(session.history)))
    queue_toast("Simulation finished — report in the chat.")
    return True


def render_simulation(session: SimulationSession, is_dark: bool, ollama_ok: bool, locked: bool) -> DeltaGenerator:
    """Draws the two main columns: the map and the orchestrator.

    The orchestrator goes first: Streamlit shows each element as it is sent, and
    the map takes about half a second to build, so the operator's message and
    the confirmation gate's state reach the screen before it.

    Args:
        session (SimulationSession): Active simulation.
        is_dark (bool): Whether the dark theme is on.
        ollama_ok (bool): Whether Ollama is reachable.
        locked (bool): Whether the controls are held while work is in flight.

    Returns:
        DeltaGenerator: The conversation's container, which the reply in flight is drawn into.
    """
    col_map, col_chat = st.columns([7, 5])

    with col_chat:
        chat_container = render_chat_panel(session, ollama_ok, locked)

    with col_map:
        render_map(session, is_dark, locked)

    return chat_container


def work_after_drawing(session: SimulationSession, agent_mode: str | None, chat_container: DeltaGenerator) -> None:
    """Answers the operator's prompt or runs the next scheduled step, then reloads to show the result.

    Both are left until the page is drawn, so the operator watches the page they
    asked from rather than the previous one while the work runs. The reload also
    clears what this render drew and the next will not: Streamlit trims a slot
    left empty only when a render ends without one, so a render that reloads
    keeps the previous render's progress strip, and the render after the last
    step, which reloads nothing, is the one that removes it.

    Args:
        session (SimulationSession): Active simulation.
        agent_mode (str): The agent's action mode, or None if disabled.
        chat_container: The conversation's container, which the reply in flight is drawn into.
    """
    answer_pending_prompt(session, agent_mode, chat_container)

    if session.has_pending_steps():
        run_scheduled_step(session)
        st.rerun()


def main_app() -> None:
    """Runs the Streamlit app."""
    st.set_page_config(page_title="LEOSim Dashboard", page_icon="🛰️", layout="wide", initial_sidebar_state="expanded")

    session_init()

    # Taking the operator's message and their answer to a proposal before
    # anything is drawn, so this render already shows them and holds the
    # controls, instead of drawing the page once more first.
    take_submitted_prompt()
    take_gate_decision()

    is_dark = st.session_state["is_dark"]
    apply_theme(is_dark)

    ollama_ok = ollama_setup()

    # Holding every control while the agent is answering or steps are running.
    # Streamlit stops the running script on any widget interaction, and the
    # sidebar and the confirmation gate stay clickable through the whole run
    # because the page is redrawn between steps.
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

    chat_container = None
    if session is None:
        with dashboard_slot:
            st.info("👈 Please configure and initialize the simulation in the sidebar to begin.")
    else:
        with action_slot:
            if resolve_pending_action(session):
                st.rerun()

        if session.has_pending_steps():
            with progress_slot:
                render_stepping_progress(session)

        # Before the dashboard is drawn, so the report lands in the chat this
        # render instead of appearing one render late.
        report_finished_plan(session)

        with notice_slot:
            toast_message = consume_toast()
            if toast_message:
                st.toast(toast_message, icon="✅")

        # Drawing the dashboard through the run as well. Skipping it left the
        # previous render's map and orchestrator on the page as a ghost: the
        # chat input is gone, so the rule that paints the orchestrator column
        # stops matching and everything in it flattens against the page, while
        # the chat avatars keep their own background and stay bright. The
        # operator gets to watch the network move, which is the point of stepping.
        with dashboard_slot:
            chat_container = render_simulation(session, is_dark, ollama_ok, locked)

    inject_css(is_dark)

    # Injecting the page scripts: the accessibility fixes, the slash menu and the theme fade.
    inject_page_scripts()

    if session is not None and chat_container is not None:
        work_after_drawing(session, sim_options["agent_mode"], chat_container)


if __name__ == "__main__":
    main_app()
