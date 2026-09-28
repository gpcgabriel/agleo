from math import atan2, radians, degrees, sin, cos
from ..ground_station import GroundStation
from geopy.distance import geodesic
from geopy.point import Point
from random import choice


# Calculating the bearing between two points.
def calculate_bearing(origin, destination):
    lat1, lon1 = map(radians, origin)
    lat2, lon2 = map(radians, destination)

    diff_long = lon2 - lon1
    x = sin(diff_long) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(diff_long)

    bearing = atan2(x, y)
    return (degrees(bearing) + 360) % 360  # Converting the angle to the 0-360 range.


def random_mobility_model(user: object):
    parameters = user.mobility_model_parameters
    station = choice(GroundStation.all())

    total_distance = geodesic(user.coordinates[:2], station.coordinates[:2]).kilometers
    num_steps = int(total_distance // parameters.get("step_km", 0.5))

    num_steps = num_steps if num_steps > 0 else 1

    points = []
    start_point = Point(user.coordinates[:2])

    # Obtaining the bearing.
    bearing = calculate_bearing(user.coordinates[:2], station.coordinates[:2])

    for i in range(1, num_steps + 1):
        fraction = i / (num_steps + 1)

        point = geodesic(kilometers=fraction * total_distance).destination(start_point, bearing)

        points.extend([(point.latitude, point.longitude, 0) for _ in range(parameters.get("steps_to_move", 1))])

    user.coordinates_trace.extend(points)
