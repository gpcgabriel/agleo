"""Catalog of satellite traces.

Loads a traces file once, indexes its positions, and answers lookups from
that index.
"""

from json import load

import numpy as np
from geopy.distance import geodesic
from leosim.components import Satellite

EARTH_RADIUS_KM = 6371.0

# A satellite's internal id is sequential (1, 2, 3...), assigned by the class
# counter. The identifier in the traces file ("satid", from the NORAD
# catalog) is a different numbering, and it does not survive the
# export()/Simulator.initialize round trip because `export()` does not keep
# the name. It is therefore recorded separately, in this attribute, whenever
# the operator creates a satellite.
CATALOG_ID_ATTRIBUTE = "catalog_id"


def get_taken_catalog_ids():
    """Returns: set: Catalog ids already used by satellites in the simulation."""
    taken = set()

    for satellite in Satellite.all():
        catalog_id = getattr(satellite, CATALOG_ID_ATTRIBUTE, None)
        if catalog_id is not None:
            taken.add(catalog_id)

    return taken


class SatelliteCatalog:
    """Satellite positions read from a traces file.

    The file is a list of steps; each step is a list of satellites carrying
    "satid", "satlat", "satlng" and "satalt".
    """

    # How many nearest candidates by the haversine formula go through the
    # exact geodesic calculation. The two measures differ by less than 1%
    # (Earth's flattening), so the final pick would only change if more than
    # 25 satellites tied within that margin.
    GEODESIC_CANDIDATES = 25

    def __init__(self, path):
        """Args:
            path (str): Path to the JSON traces file.
        """
        self.path = path

        with open(path, "r", encoding="UTF-8") as file:
            steps = load(file)

        latitudes = []
        longitudes = []
        altitudes = []
        catalog_ids = []

        # positions_by_id holds each satellite's path in step order; it is
        # what answers trace lookups.
        self.positions_by_id = {}

        for step in steps:
            for satellite in step:
                catalog_id = satellite["satid"]
                position = (satellite["satlat"], satellite["satlng"], satellite["satalt"])

                latitudes.append(position[0])
                longitudes.append(position[1])
                altitudes.append(position[2])
                catalog_ids.append(catalog_id)

                self.positions_by_id.setdefault(catalog_id, []).append(position)

        self.latitudes = np.array(latitudes, dtype=float)
        self.longitudes = np.array(longitudes, dtype=float)
        self.altitudes = np.array(altitudes, dtype=float)
        self.catalog_ids = np.array(catalog_ids)
        self.step_count = len(steps)

    def count_satellites(self):
        """Returns: int: How many distinct satellites the file holds."""
        return len(self.positions_by_id)

    def count_positions(self):
        """Returns: int: How many positions are indexed in total."""
        return len(self.latitudes)

    def _haversine_to_all(self, target_lat, target_lon):
        """Approximate distance from the target to every indexed position.

        Used only to rank candidates; the final distance is computed with
        geodesic precision.

        Returns:
            numpy.ndarray: Distances in kilometres.
        """
        target_lat_rad = np.radians(target_lat)
        target_lon_rad = np.radians(target_lon)
        latitudes_rad = np.radians(self.latitudes)
        longitudes_rad = np.radians(self.longitudes)

        delta_lat = latitudes_rad - target_lat_rad
        delta_lon = longitudes_rad - target_lon_rad

        inner = (
            np.sin(delta_lat / 2.0) ** 2
            + np.cos(target_lat_rad) * np.cos(latitudes_rad) * np.sin(delta_lon / 2.0) ** 2
        )
        return 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(inner, 0.0, 1.0)))

    def get_closest_satellite(self, target_coord, exclude_ids=None):
        """Finds the free satellite that passes closest to a point.

        Args:
            target_coord (tuple): Reference point (lat, lon, ...).
            exclude_ids (set): Catalog ids to skip.

        Returns:
            tuple: (catalog id, position) at the point of closest approach, or
            (None, None) if every satellite is excluded.
        """
        exclude_ids = set(exclude_ids or ())
        distances = self._haversine_to_all(target_coord[0], target_coord[1])

        if exclude_ids:
            excluded = np.isin(self.catalog_ids, list(exclude_ids))
            distances = np.where(excluded, np.inf, distances)

        finite = np.isfinite(distances)
        if not finite.any():
            return None, None

        candidate_count = min(self.GEODESIC_CANDIDATES, int(finite.sum()))
        candidates = np.argpartition(distances, candidate_count - 1)[:candidate_count]

        target_lat_lon = (target_coord[0], target_coord[1])
        best_index = None
        best_distance = float("inf")

        for index in candidates:
            if not np.isfinite(distances[index]):
                continue

            distance = geodesic(target_lat_lon, (self.latitudes[index], self.longitudes[index])).kilometers
            if distance < best_distance:
                best_distance = distance
                best_index = index

        if best_index is None:
            return None, None

        position = (
            float(self.latitudes[best_index]),
            float(self.longitudes[best_index]),
            float(self.altitudes[best_index]),
        )
        return self.catalog_ids[best_index].item(), position

    def get_coordinates_trace(self, catalog_id, start_position):
        """Builds a satellite's path starting from a given position.

        Args:
            catalog_id: Catalog id of the satellite.
            start_position (tuple): Position the path starts from.

        Returns:
            list: Successive positions, starting at `start_position`. If that
            position is not part of the path, returns just that position.
        """
        positions = self.positions_by_id.get(catalog_id)
        if not positions:
            return [start_position]

        for index, position in enumerate(positions):
            if position == tuple(start_position):
                return positions[index:]

        return [start_position]

    def __repr__(self):
        return (
            f"SatelliteCatalog(path={self.path!r}, satellites={self.count_satellites()}, "
            f"steps={self.step_count}, positions={self.count_positions()})"
        )


# The traces file does not change while the app runs and takes a few seconds
# to index, so each path is loaded once per process.
_LOADED_CATALOGS = {}


def get_catalog(path):
    """Returns the catalog for a file, loading it on the first call.

    Args:
        path (str): Path to the JSON traces file.

    Returns:
        SatelliteCatalog: The matching catalog.
    """
    if path not in _LOADED_CATALOGS:
        _LOADED_CATALOGS[path] = SatelliteCatalog(path)

    return _LOADED_CATALOGS[path]
