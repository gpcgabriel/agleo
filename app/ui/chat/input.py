"""The operator's command field."""

import streamlit as st

from app.agents.dashboard.runner import run_agent
from app.core.router import Blocked, DispatchToAgent, LocalReply, route
from app.core.snapshot import find_default_node_position
from app.helper_functions.ollama_helper import DEFAULT_MODEL, model_is_available
from app.ui.state import (
    clear_prompt_for_agent,
    get_pending,
    get_prompt_for_agent,
    push_chat,
    set_pending,
    set_prompt_for_agent,
)

BUSY_PLACEHOLDER = "⏳ Simulation in progress..."
NO_OLLAMA_PLACEHOLDER = "⚠️ Agent unavailable — Ollama not running"
READY_PLACEHOLDER = "Type a command for the agent (e.g., 'Advance simulation by 3 steps')"
THINKING_PLACEHOLDER = "🤖 Agent is answering..."


def resolve_input_state(session, ollama_ok):
    """Decides the command field's placeholder text and availability.

    Returns:
        tuple: (placeholder, disabled).
    """
    if get_prompt_for_agent() is not None:
        return THINKING_PLACEHOLDER, True

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
        chat_container: History container the spinner is drawn into.
    """
    placeholder, disabled = resolve_input_state(session, ollama_ok)

    submitted = st.chat_input(placeholder, disabled=disabled, key="agent_chat_input")
    if submitted:
        # Handing the prompt to the next render rather than answering here, so
        # the controls that can interrupt a running script are drawn disabled
        # before the call starts.
        push_chat("user", submitted)
        set_prompt_for_agent(submitted)
        st.rerun()

    prompt = get_prompt_for_agent()
    if prompt is None:
        return

    decision = route(prompt, session, has_pending_action=get_pending() is not None)

    try:
        with chat_container:
            answer_decision(decision, prompt, session, agent_mode)
    finally:
        clear_prompt_for_agent()

    st.rerun()


def answer_decision(decision, prompt, session, agent_mode):
    """Records the reply matching the router's decision in the history.

    Nothing is drawn here beyond the spinner: the reply is appended to the
    history and the caller reloads, so the answer survives even if the render
    it was produced on is cut short.

    Args:
        decision: What `route` returned for this prompt.
        prompt (str): What the operator submitted.
        session (SimulationSession): Active simulation.
        agent_mode (str): The agent's action mode.

    Raises:
        ValueError: If the decision is of an unknown type.
    """
    if isinstance(decision, LocalReply):
        push_chat("assistant", decision.text)
        return

    if isinstance(decision, Blocked):
        push_chat("system", decision.reason)
        return

    if isinstance(decision, DispatchToAgent):
        with st.spinner("🤖 Agent calculating response (Inference)..."):
            result = run_agent(
                prompt,
                st.session_state.get("selected_model", DEFAULT_MODEL),
                # A command the router classified as a question is answered by
                # an agent with no way to act, so it cannot propose one anyway.
                agent_mode if decision.allows_changes else None,
                decision.context_state,
                current_config=session.config,
                default_position=find_default_node_position(session.get_current_snapshot()),
            )

            # Storing before leaving the spinner. Only session state is touched
            # from here, so a rerun queued while the model was answering cannot
            # discard the answer.
            push_chat("assistant", result.text)

            proposal = result.get_primary_proposal()
            if proposal is not None:
                set_pending(proposal)
        return

    raise ValueError(f"Unknown routing decision: {type(decision).__name__}.")
