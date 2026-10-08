"""Geographic constants and distances shared by the engine and the application.

Coordinates throughout the simulator are (latitude, longitude, altitude), with
latitude and longitude in degrees and altitude in kilometres.
"""

import math
from collections.abc import Sequence

from geopy.distance import geodesic

# Holding a position as (latitude, longitude, altitude): a tuple in memory, a list once a scenario
# file is read back.
Coordinates = Sequence[float]

MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0
ALTITUDE_INDEX = 2


def slant_range(origin: Coordinates, target: Coordinates) -> float:
    """Returns the straight-line distance between two positions, in kilometres.

    The ground leg is the geodesic between the two (latitude, longitude) pairs and
    the vertical leg the difference of the altitudes, both already in kilometres,
    so the altitude enters unscaled.

    Args:
        origin (tuple): (latitude, longitude, altitude) of one end.
        target (tuple): (latitude, longitude, altitude) of the other end.

    Returns:
        float: The distance in kilometres.
    """
    ground_distance = geodesic(origin[:2], target[:2]).kilometers
    air_distance = origin[ALTITUDE_INDEX] - target[ALTITUDE_INDEX]
    return math.sqrt(ground_distance**2 + air_distance**2)
