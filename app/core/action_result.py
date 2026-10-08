"""Outcome of executing a proposed action."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.session import SimulationSession


class ActionResult:
    """What an action produced, without deciding how it is displayed.

    The handler returns messages and, where applicable, a replacement
    session; the interface is what writes to the chat, raises the toast and
    swaps the active session.
    """

    def __init__(
        self,
        messages: list[dict[str, str]] | None = None,
        toast: str | None = None,
        new_session: SimulationSession | None = None,
    ) -> None:
        """Args:
        messages (list): Messages to append to the conversation history.
        toast (str): Short notice to display, if any.
        new_session (SimulationSession): Session replacing the current one,
            when the action rebuilt the simulation.
        """
        self.messages = list(messages or [])
        self.toast = toast
        self.new_session = new_session

    def replaces_session(self) -> bool:
        """Returns: bool: True if the action swapped the active simulation."""
        return self.new_session is not None
