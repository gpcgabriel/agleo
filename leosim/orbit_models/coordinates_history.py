from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..components.satellite import Satellite
    from ..geometry import Coordinates


def coordinates_history(satellite: Satellite) -> Coordinates | None:
    """Returns the satellite's position for the current step by replaying its recorded trace in a loop.

    The recording is taken as one period of the orbit: its length is kept in the
    model's parameters under "len", which a scenario may also set, and the
    position `step` ticks in is the one recorded at `step % len`.

    Args:
        satellite (Satellite): The satellite to move.

    Returns:
        tuple or None: The recorded position, or None where the recording has a gap.

    Raises:
        ValueError: If the period is not a length the recorded trace holds.
    """
    period = satellite.mobility_model_parameters.setdefault("len", len(satellite.coordinates_trace))

    if not 0 < period <= len(satellite.coordinates_trace):
        raise ValueError(
            f"Invalid period for {satellite}: {period!r}. coordinates_history replays a recorded trace, "
            f"so it expects between 1 and the {len(satellite.coordinates_trace)} positions recorded."
        )

    return satellite.coordinates_trace[satellite.model.scheduler.steps % period]
