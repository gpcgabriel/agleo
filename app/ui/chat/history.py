"""Conversation history between the operator and the agent."""

import streamlit as st

from app.ui.gui.icons import icon_bot, wrap_icon
from app.ui.state import CHAT_KEY

CHAT_HEIGHT = 450


def render_chat_history():
    """Draws the message history.

    Returns:
        DeltaGenerator: The history container, so the in-flight reply can be
        written inside it.
    """
    container = st.container(height=CHAT_HEIGHT)

    with container:
        for message in st.session_state[CHAT_KEY]:
            if message["role"] == "system":
                st.markdown(
                    f'<div class="system-msg">{wrap_icon(icon_bot(16))} {message["content"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    return container
