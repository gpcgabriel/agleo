import streamlit as st

from app.helper_functions.ollama_helper import DEFAULT_MODEL


def session_init() -> None:
    """Initialize every st.session_state key used across the app"""
    if "toast_message" in st.session_state and st.session_state["toast_message"]:
        st.toast(st.session_state["toast_message"], icon="✅")
        del st.session_state["toast_message"]

    if "is_dark" not in st.session_state:
        st.session_state["is_dark"] = True

    if "simulation_history" not in st.session_state:
        st.session_state["simulation_history"] = []
    if "current_step_index" not in st.session_state:
        st.session_state["current_step_index"] = 0
    if "pending_action" not in st.session_state:
        st.session_state["pending_action"] = None
    if "chat_messages" not in st.session_state:
        st.session_state["chat_messages"] = [
            {
                "role": "assistant",
                "content": "Hello! I'm the LEOSim constellation control assistant. Enable the tools in the sidebar and use the chat to send me commands.",
            }
        ]
    if "simulator" not in st.session_state:
        st.session_state["simulator"] = None
    if "success_banner" not in st.session_state:
        st.session_state["success_banner"] = None
    if "steps_remaining" not in st.session_state:
        st.session_state["steps_remaining"] = 0
    if "selected_model" not in st.session_state:
        st.session_state["selected_model"] = DEFAULT_MODEL
