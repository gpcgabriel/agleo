"""Orchestrator column: confirmation gate, history and command field."""

import streamlit as st

from app.ui.chat.gate import render_confirmation_gate
from app.ui.chat.history import render_chat_history
from app.ui.chat.input import render_chat_input
from app.ui.gui.icons import icon_bot, wrap_icon


def render_chat_panel(session, agent_mode, ollama_ok):
    """Draws the orchestrator column.

    Args:
        session (SimulationSession): Active simulation.
        agent_mode (str): "Tools", "Skills", or None when the agent's actions
            are disabled.
        ollama_ok (bool): Whether Ollama is reachable.
    """
    st.markdown(f"<h3>{wrap_icon(icon_bot(20))} Agent Orchestrator</h3>", unsafe_allow_html=True)

    render_confirmation_gate()
    chat_container = render_chat_history()
    render_chat_input(session, agent_mode, ollama_ok, chat_container)
