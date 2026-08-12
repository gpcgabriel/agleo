from typing import Tuple

def linear_estimation(sat) -> Tuple[float, float, float]:
    """
    Estimates the next position of the satellite based on linear inertia.
    Purely mathematical model: receives the state and returns the new coordinate.
    It has no side effects on the satellite's temporal mesh (coordinates_trace).
    """
    curr_lat, curr_lon, curr_alt = sat.coordinates

    last_coord = sat.mobility_model_parameters.get("last_coordinate")

    if last_coord is None:
        current_step = sat.model.scheduler.steps
        
        if current_step >= 2:
            last_coord = sat.coordinates_trace[current_step - 2]
        else:
            last_coord = sat.coordinates

    last_lat, last_lon, _ = last_coord

    delta_lat = curr_lat - last_lat
    delta_lon = curr_lon - last_lon

    sat.mobility_model_parameters["last_coordinate"] = sat.coordinates

    new_lat = curr_lat + delta_lat
    new_lon = curr_lon + delta_lon

    if new_lat > 90.0:
        new_lat = 180.0 - new_lat
        new_lon += 180.0
    elif new_lat < -90.0:
        new_lat = -180.0 - new_lat
        new_lon += 180.0

    new_lon = (new_lon + 180.0) % 360.0 - 180.0

    return (new_lat, new_lon, curr_alt)