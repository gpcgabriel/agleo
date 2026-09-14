"""The operator's command field."""

import streamlit as st

from app.agents.runner import run_agent
from app.core.router import Blocked, DispatchToAgent, LocalReply, route
from app.helper_functions.ollama_helper import DEFAULT_MODEL, model_is_available
from app.ui.state import get_pending, push_chat, set_pending

BUSY_PLACEHOLDER = "⏳ Simulation in progress..."
NO_OLLAMA_PLACEHOLDER = "⚠️ Agent unavailable — Ollama not running"
READY_PLACEHOLDER = "Type a command for the agent (e.g., 'Advance simulation by 3 steps')"


def resolve_input_state(session, ollama_ok):
    """Decides the command field's placeholder text and availability.

    Returns:
        tuple: (placeholder, disabled).
    """
    if session.has_pending_steps():
        return BUSY_PLACEHOLDER, True

    if not ollama_ok:
        return NO_OLLAMA_PLACEHOLDER, True

    selected_model = st.session_state.get("selected_model", DEFAULT_MODEL)
    if not model_is_available(selected_model):
        return f"⚠️ Agent unavailable — Model '{selected_model}' not downloaded", True

    return READY_PLACEHOLDER, False


def render_chat_input(session, agent_mode, ollama_ok, chat_container):
    """Draws the command field and handles whatever the operator submits.

    Args:
        session (SimulationSession): Active simulation.
        agent_mode (str): The agent's action mode, or None if disabled.
        ollama_ok (bool): Whether Ollama is reachable.
        chat_container: History container the reply is drawn into.
    """
    placeholder, disabled = resolve_input_state(session, ollama_ok)

    prompt = st.chat_input(placeholder, disabled=disabled, key="agent_chat_input")
    if not prompt:
        return

    push_chat("user", prompt)
    decision = route(prompt, session, has_pending_action=get_pending() is not None)

    with chat_container:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            response = _render_decision(decision, prompt, session, agent_mode)

    push_chat("assistant", response)
    st.rerun()


def _render_decision(decision, prompt, session, agent_mode):
    """Draws the reply matching the router's decision.

    Returns:
        str: The text to store in the history.
    """
    if isinstance(decision, LocalReply):
        st.markdown(decision.text)
        return decision.text

    if isinstance(decision, Blocked):
        st.warning(decision.reason)
        return decision.reason

    if isinstance(decision, DispatchToAgent):
        with st.spinner("🤖 Agent calculating response (Inference)..."):
            result = run_agent(
                prompt,
                st.session_state.get("selected_model", DEFAULT_MODEL),
                agent_mode,
                decision.context_state,
                current_config=session.config,
            )

        st.markdown(result.text)

        proposal = result.get_primary_proposal()
        if proposal is not None:
            set_pending(proposal)

        return result.text

    raise ValueError(f"Unknown routing decision: {type(decision).__name__}.")
