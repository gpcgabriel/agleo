"""Bridge between `st.session_state` and the domain objects.

This is the only module that knows the key names Streamlit stores things
under. The rest of the interface reaches the simulation session through these
functions, so changing the state mechanism touches a single file.
"""

import streamlit as st

SESSION_KEY = "sim_session"
PENDING_KEY = "pending_action"
PENDING_CONFIRMED_KEY = "pending_action_confirmed"
TOAST_KEY = "toast_message"
CHAT_KEY = "chat_messages"


# -- Simulation session -----------------------------------------------------

def get_session():
    """Returns: SimulationSession or None: The loaded simulation, if any."""
    return st.session_state.get(SESSION_KEY)


def set_session(session):
    """Args: session (SimulationSession): Simulation that becomes the active one."""
    st.session_state[SESSION_KEY] = session


def has_session():
    """Returns: bool: True if a simulation is loaded."""
    return get_session() is not None


def require_session():
    """Returns: SimulationSession: The active simulation.

    Raises:
        RuntimeError: If no simulation has been initialized.
    """
    session = get_session()
    if session is None:
        raise RuntimeError("No simulation has been initialized.")
    return session


# -- Conversation and notices -----------------------------------------------

def push_chat(role, content):
    """Appends a message to the conversation history.

    Args:
        role (str): "user", "assistant" or "system".
        content (str): Message text.
    """
    st.session_state[CHAT_KEY].append({"role": role, "content": content})


def queue_toast(message):
    """Queues a short notice for the next render.

    Args:
        message (str): Notice text.
    """
    st.session_state[TOAST_KEY] = message


def consume_toast():
    """Returns the queued notice and removes it from the queue.

    Returns:
        str or None: The notice, if one was queued.
    """
    message = st.session_state.get(TOAST_KEY)
    if message:
        del st.session_state[TOAST_KEY]
    return message


def apply_result(result):
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

def get_pending():
    """Returns: ProposedAction or None: The proposal awaiting a decision."""
    return st.session_state.get(PENDING_KEY)


def set_pending(action):
    """Registers a proposal for the operator to confirm or cancel.

    Args:
        action (ProposedAction): Proposal recorded by the agent.
    """
    st.session_state[PENDING_KEY] = action
    st.session_state[PENDING_CONFIRMED_KEY] = False


def clear_pending():
    """Discards the pending proposal and its confirmation."""
    st.session_state[PENDING_KEY] = None
    st.session_state[PENDING_CONFIRMED_KEY] = False


def confirm_pending():
    """Marks the pending proposal as confirmed by the operator."""
    st.session_state[PENDING_CONFIRMED_KEY] = True


def pending_is_confirmed():
    """Returns: bool: True if there is a confirmed proposal waiting to run."""
    return get_pending() is not None and st.session_state.get(PENDING_CONFIRMED_KEY, False)
