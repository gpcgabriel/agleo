"""The operator's command field."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
CHAT_INPUT_KEY = "agent_chat_input"


if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

    from app.core.session import SimulationSession


def resolve_input_state(session: SimulationSession, ollama_ok: bool) -> tuple[str, bool]:
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


def take_submitted_prompt() -> None:
    """Records what the operator just submitted, before anything else is drawn.

    Streamlit holds the submitted text under the field's key from the start of
    the render the submission triggers. Recording it here, at the top, puts the
    message in the history and draws the controls held on this same render,
    instead of after the sidebar and the map have been drawn once more.
    """
    submitted = st.session_state.get(CHAT_INPUT_KEY)
    if submitted:
        push_chat("user", submitted)
        set_prompt_for_agent(submitted)


def render_chat_input(session: SimulationSession, ollama_ok: bool) -> None:
    """Draws the command field; `take_submitted_prompt` records what it submits.

    Args:
        session (SimulationSession): Active simulation.
        ollama_ok (bool): Whether Ollama is reachable.
    """
    placeholder, disabled = resolve_input_state(session, ollama_ok)
    st.chat_input(placeholder, disabled=disabled, key=CHAT_INPUT_KEY)


def answer_pending_prompt(session: SimulationSession, agent_mode: str | None, chat_container: DeltaGenerator) -> None:
    """Answers the recorded prompt, once the page is drawn, and reloads to show the reply.

    Args:
        session (SimulationSession): Active simulation.
        agent_mode (str): The agent's action mode, or None if disabled.
        chat_container: History container the spinner is drawn into.
    """
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


def answer_decision(
    decision: LocalReply | Blocked | DispatchToAgent, prompt: str, session: SimulationSession, agent_mode: str | None
) -> None:
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
    match decision:
        case LocalReply():
            push_chat("assistant", decision.text)

        case Blocked():
            push_chat("system", decision.reason)

        case DispatchToAgent():
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

        case _:
            raise ValueError(f"Unknown routing decision: {type(decision).__name__}.")
