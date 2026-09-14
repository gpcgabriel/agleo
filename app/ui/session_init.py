"""Initialization of every key the app keeps in `st.session_state`."""

import streamlit as st

from app.helper_functions.ollama_helper import DEFAULT_MODEL
from app.ui.state import CHAT_KEY, PENDING_CONFIRMED_KEY, PENDING_KEY, SESSION_KEY, TOAST_KEY

WELCOME_MESSAGE = (
    "Hello! I'm the LEOSim constellation control assistant. "
    "Enable the tools in the sidebar and use the chat to send me commands."
)


def session_init() -> None:
    """Seeds the session state keys the app reads on every render.

    The simulation itself (simulator, history, viewed step and scheduled
    steps) lives inside a SimulationSession under a single key, not in
    separate entries.
    """
    if "is_dark" not in st.session_state:
        st.session_state["is_dark"] = True

    if SESSION_KEY not in st.session_state:
        st.session_state[SESSION_KEY] = None

    if PENDING_KEY not in st.session_state:
        st.session_state[PENDING_KEY] = None

    if PENDING_CONFIRMED_KEY not in st.session_state:
        st.session_state[PENDING_CONFIRMED_KEY] = False

    if CHAT_KEY not in st.session_state:
        st.session_state[CHAT_KEY] = [{"role": "assistant", "content": WELCOME_MESSAGE}]

    if TOAST_KEY not in st.session_state:
        st.session_state[TOAST_KEY] = None

    if "selected_model" not in st.session_state:
        st.session_state["selected_model"] = DEFAULT_MODEL
