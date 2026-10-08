from __future__ import annotations

from typing import TYPE_CHECKING

from ..geometry import MAX_LATITUDE

if TYPE_CHECKING:
    from ..components.satellite import Satellite

# Estimating a velocity takes two recorded positions: the current one and the one before.
POSITIONS_FOR_A_VELOCITY = 2


def linear_estimation(sat: Satellite) -> tuple[float, float, float] | None:
    """Estimates the satellite's next position by repeating its last displacement.

    Purely mathematical: it receives the state and returns the new coordinate,
    leaving the trace (coordinates_trace) to the satellite. A satellite the
    capture has not seen yet has no position and keeps none, and one with no
    earlier position to take a velocity from stands still.

    Args:
        sat (Satellite): The satellite to move.

    Returns:
        tuple or None: The estimated (latitude, longitude, altitude), or None while the satellite has no position.
    """
    if sat.coordinates is None:
        return None
    curr_lat, curr_lon, curr_alt = sat.coordinates

    last_coord = sat.mobility_model_parameters.get("last_coordinate")

    if last_coord is None:
        current_step = sat.model.scheduler.steps
        earlier = (
            sat.coordinates_trace[current_step - POSITIONS_FOR_A_VELOCITY]
            if current_step >= POSITIONS_FOR_A_VELOCITY
            else None
        )
        # Standing still when that slot is empty, as it is right after the steps before a first sighting.
        last_coord = earlier if earlier is not None else sat.coordinates

    last_lat, last_lon, _ = last_coord

    delta_lat = curr_lat - last_lat
    delta_lon = curr_lon - last_lon

    sat.mobility_model_parameters["last_coordinate"] = sat.coordinates

    new_lat = curr_lat + delta_lat
    new_lon = curr_lon + delta_lon

    if new_lat > MAX_LATITUDE:
        new_lat = 180.0 - new_lat
        new_lon += 180.0
    elif new_lat < -MAX_LATITUDE:
        new_lat = -180.0 - new_lat
        new_lon += 180.0

    new_lon = (new_lon + 180.0) % 360.0 - 180.0

    return (new_lat, new_lon, curr_alt)
