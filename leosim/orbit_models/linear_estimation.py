from geopy.distance import geodesic
import math

def linear_estimation(sat):
    last_lat, last_lon, alt = sat.mobility_model_parameters["last_coordinate"]
    new_lat, new_lon, new_alt = sat.coordinates

    # Get points distance in miles
    speed_ns = geodesic((last_lat, last_lon), (new_lat, last_lon)).miles
    speed_ew = geodesic((last_lat, last_lon), (last_lat, new_lon)).miles

    # Convert miles to degrees
    speed_ns /= 69
    speed_ew /= (69 * abs(math.cos(math.radians(last_lat))))

    # Update coordinates
    sat.mobility_model_parameters["last_coordinate"] = sat.coordinates
    new_lat = (new_lat + speed_ns + 85) % 170 - 85
    new_lon = (new_lon + speed_ew + 180) % 360 - 180

    new_coord = (new_lat, new_lon, new_alt)

    sat.coordinates = new_coord

    current_step = sat.model.scheduler.steps
    
    if not hasattr(sat, "coordinates_trace") or sat.coordinates_trace is None:
        sat.coordinates_trace = []
    
    while len(sat.coordinates_trace) <= current_step:
        sat.coordinates_trace.append(new_coord)
        
    sat.coordinates_trace[current_step] = new_coord