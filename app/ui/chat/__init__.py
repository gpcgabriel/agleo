"""Orchestrator column: confirmation gate, history and command field."""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

from app.ui.chat.gate import render_confirmation_gate, take_gate_decision
from app.ui.chat.history import render_chat_history
from app.ui.chat.input import answer_pending_prompt, render_chat_input, take_submitted_prompt
from app.ui.gui.icons import icon_bot, wrap_icon
from app.ui.state import get_pending

if TYPE_CHECKING:
    from streamlit.delta_generator import DeltaGenerator

    from app.core.session import SimulationSession

__all__ = ["answer_pending_prompt", "render_chat_panel", "take_gate_decision", "take_submitted_prompt"]


def render_chat_panel(session: SimulationSession, ollama_ok: bool, locked: bool = False) -> DeltaGenerator:
    """Draws the orchestrator column.

    Args:
        session (SimulationSession): Active simulation.
        ollama_ok (bool): Whether Ollama is reachable.
        locked (bool): Whether the controls are held while work is in flight.

    Returns:
        DeltaGenerator: The history container, which the reply in flight is drawn into.
    """
    st.markdown(f"<h3>{wrap_icon(icon_bot(20))} Agent Orchestrator</h3>", unsafe_allow_html=True)

    # Reserving the gate's place whether or not a proposal is pending, for the
    # reason the slots in `app.py` exist: it is drawn on some renders and not
    # others, and without a place of its own it shifts the conversation below
    # it. The place is an `st.empty` rather than a container: redrawn empty, it
    # drops the box at once, where a container keeps the box until a render
    # ends without a rerun, which kept it on screen through a whole run.
    gate_slot = st.empty()
    if get_pending() is not None:
        with gate_slot.container():
            render_confirmation_gate(locked)

    chat_container = render_chat_history()
    render_chat_input(session, ollama_ok)
    return chat_container
