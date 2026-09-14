"""Outcome of executing a proposed action."""


class ActionResult:
    """What an action produced, without deciding how it is displayed.

    The handler returns messages and, where applicable, a replacement
    session; the interface is what writes to the chat, raises the toast and
    swaps the active session.
    """

    def __init__(self, messages=None, toast=None, new_session=None):
        """Args:
            messages (list): Messages to append to the conversation history.
            toast (str): Short notice to display, if any.
            new_session (SimulationSession): Session replacing the current one,
                when the action rebuilt the simulation.
        """
        self.messages = list(messages or [])
        self.toast = toast
        self.new_session = new_session

    def replaces_session(self):
        """Returns: bool: True if the action swapped the active simulation."""
        return self.new_session is not None
