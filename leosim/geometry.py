"""Geographic constants shared by the engine and the application.

Coordinates throughout the simulator are (latitude, longitude, altitude), with
latitude and longitude in degrees and altitude in kilometres.
"""

from collections.abc import Sequence

# Holding a position as (latitude, longitude, altitude): a tuple in memory, a list once a scenario
# file is read back.
Coordinates = Sequence[float]

MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0
ALTITUDE_INDEX = 2
