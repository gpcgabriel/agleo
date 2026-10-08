"""Bridge between `st.session_state` and the domain objects.

This is the only module that knows the key names Streamlit stores things
under. The rest of the interface reaches the simulation session through these
functions, so changing the state mechanism touches a single file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import streamlit as st

if TYPE_CHECKING:
    from app.core.action_result import ActionResult
    from app.core.actions import ProposedAction
    from app.core.session import SimulationSession

SESSION_KEY = "sim_session"
PENDING_KEY = "pending_action"
PENDING_CONFIRMED_KEY = "pending_action_confirmed"
TOAST_KEY = "toast_message"
CHAT_KEY = "chat_messages"
PROMPT_KEY = "prompt_awaiting_agent"


# -- Simulation session -----------------------------------------------------


def get_session() -> SimulationSession | None:
    """Returns: SimulationSession or None: The loaded simulation, if any."""
    return st.session_state.get(SESSION_KEY)


def set_session(session: SimulationSession | None) -> None:
    """Args: session (SimulationSession): Simulation that becomes the active one."""
    st.session_state[SESSION_KEY] = session


# -- Conversation and notices -----------------------------------------------


def push_chat(role: str, content: str) -> None:
    """Appends a message to the conversation history.

    Args:
        role (str): "user", "assistant" or "system".
        content (str): Message text.
    """
    st.session_state[CHAT_KEY].append({"role": role, "content": content})


def queue_toast(message: str) -> None:
    """Queues a short notice for the next render.

    Args:
        message (str): Notice text.
    """
    st.session_state[TOAST_KEY] = message


def consume_toast() -> str | None:
    """Returns the queued notice and removes it from the queue.

    Returns:
        str or None: The notice, if one was queued.
    """
    message = st.session_state.get(TOAST_KEY)
    if message:
        del st.session_state[TOAST_KEY]
    return message


def apply_result(result: ActionResult) -> None:
    """Reflects what an action produced onto the interface.

    Args:
        result (ActionResult): Result returned by the executor.
    """
    for message in result.messages:
        push_chat(message["role"], message["content"])

    if result.toast:
        queue_toast(result.toast)

    if result.replaces_session():
        set_session(result.new_session)


# -- Pending proposal -------------------------------------------------------


def get_pending() -> ProposedAction | None:
    """Returns: ProposedAction or None: The proposal awaiting a decision."""
    return st.session_state.get(PENDING_KEY)


def set_pending(action: ProposedAction) -> None:
    """Registers a proposal for the operator to confirm or cancel.

    Args:
        action (ProposedAction): Proposal recorded by the agent.
    """
    st.session_state[PENDING_KEY] = action
    st.session_state[PENDING_CONFIRMED_KEY] = False


def clear_pending() -> None:
    """Discards the pending proposal and its confirmation."""
    st.session_state[PENDING_KEY] = None
    st.session_state[PENDING_CONFIRMED_KEY] = False


def confirm_pending() -> None:
    """Marks the pending proposal as confirmed by the operator."""
    st.session_state[PENDING_CONFIRMED_KEY] = True


def pending_is_confirmed() -> bool:
    """Returns: bool: True if there is a confirmed proposal waiting to run."""
    return get_pending() is not None and st.session_state.get(PENDING_CONFIRMED_KEY, False)


# -- Prompt awaiting the agent ----------------------------------------------


def set_prompt_for_agent(prompt: str) -> None:
    """Records a prompt for the agent to answer once the page is drawn.

    Answering takes tens of seconds, and Streamlit stops a running script the
    moment any widget is touched. Recording the prompt before the page is drawn
    lets the controls that would interrupt the answer be drawn disabled first.

    Args:
        prompt (str): What the operator submitted.
    """
    st.session_state[PROMPT_KEY] = prompt


def get_prompt_for_agent() -> str | None:
    """Returns: str or None: The prompt this render has to answer."""
    return st.session_state.get(PROMPT_KEY)


def clear_prompt_for_agent() -> None:
    """Forgets the prompt, whether or not it was answered."""
    st.session_state[PROMPT_KEY] = None


def agent_is_running() -> bool:
    """Returns: bool: True if this render is waiting on the agent."""
    return get_prompt_for_agent() is not None
