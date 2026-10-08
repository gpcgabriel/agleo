from __future__ import annotations

from typing import TYPE_CHECKING

from ..geometry import MAX_LATITUDE

if TYPE_CHECKING:
    from ..components.satellite import Satellite

# Estimating a velocity takes two recorded positions: the current one and the one before.
POSITIONS_FOR_A_VELOCITY = 2


def linear_estimation(sat: Satellite) -> tuple[float, float, float]:
    """
    Estimates the next position of the satellite based on linear inertia.
    Purely mathematical model: receives the state and returns the new coordinate.
    It has no side effects on the satellite's temporal mesh (coordinates_trace).
    """
    if sat.coordinates is None:
        raise ValueError(f"{sat} has no current position to extrapolate the next one from.")
    curr_lat, curr_lon, curr_alt = sat.coordinates

    last_coord = sat.mobility_model_parameters.get("last_coordinate")

    if last_coord is None:
        current_step = sat.model.scheduler.steps
        last_coord = (
            sat.coordinates_trace[current_step - POSITIONS_FOR_A_VELOCITY]
            if current_step >= POSITIONS_FOR_A_VELOCITY
            else sat.coordinates
        )
        if last_coord is None:
            raise ValueError(f"{sat} has no position two steps back to estimate its velocity from.")

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
