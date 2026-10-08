"""Builders for the components of a scenario: users, applications, links and satellites.

Satellites come from a capture of the N2YO "above" endpoint: a list of steps, each the list
of satellites the API reported above a point at that moment. A traces file such as
`datasets/satellites_brazil.json` holds one, and `python -m dataset_generator` takes a new one.
"""

import os
from collections.abc import Iterator
from json import load
from random import choices
from time import sleep
from typing import TypedDict

import requests

from leosim import ComponentManager
from leosim.components import (
    Application,
    FixedDurationAccessModel,
    NetworkLink,
    Satellite,
    Topology,
    User,
    mesh_network,
)
from leosim.geometry import ALTITUDE_INDEX, Coordinates

REFERENCE_POINT = (-15.669171, -48.013922, 0)
MAX_RANGE = 1500

# Drawing the cycles of an application access from these lengths, in steps.
ACCESS_CYCLE_LENGTHS = list(range(3, 20))
ACCESS_CYCLES_DRAWN = 5

N2YO_ABOVE_URL = (
    "https://api.n2yo.com/rest/v1/satellite/above/{latitude}/{longitude}/{altitude}/{radius}/{category}/&apiKey={key}"
)
N2YO_KEY_VARIABLE = "N2YO_API_KEY"
REQUEST_TIMEOUT_SECONDS = 30
STARLINK_CATEGORY = 52
# Searching the whole sky above the horizon: N2YO measures the radius from the zenith, 0 to 90 degrees.
MAX_SEARCH_RADIUS = 90
# Waiting a minute between captures keeps a long capture under the endpoint's 100 requests an hour.
CAPTURE_INTERVAL_SECONDS = 60


class Sighting(TypedDict):
    """One satellite as the N2YO "above" endpoint reports it, and as a traces file stores it."""

    satid: int
    satname: str
    intDesignator: str
    launchDate: str
    satlat: float
    satlng: float
    satalt: float


def create_user(coordinates: Coordinates, connection_range: int = MAX_RANGE) -> User:
    """Returns a new user at the given coordinates, with no mobility model yet."""
    user = User(coordinates=coordinates, max_connection_range=connection_range)

    user.mobility_model = None
    user.mobility_model_parameters = {}

    return user


def create_application_to_user(
    user: User,
    cpu_demand: int = 0,
    memory_demand: int = 0,
    storage_demand: int = 0,
    access_class: type = FixedDurationAccessModel,
) -> Application:
    """Creates an application for a user, accessed through a model drawn at random.

    Args:
        user (User): The user who owns it.
        cpu_demand (int): CPU the application needs.
        memory_demand (int): Memory the application needs.
        storage_demand (int): Storage the application needs.
        access_class (type): The access model, `FixedDurationAccessModel` or
            `DynamicDurationAccessModel`.

    Returns:
        Application: The application, already linked to the user.
    """
    app = Application(cpu_demand=cpu_demand, memory_demand=memory_demand, storage_demand=storage_demand)

    access_model = access_class(
        user=user,
        application=app,
        start=1,
        duration_values=choices(ACCESS_CYCLE_LENGTHS, k=ACCESS_CYCLES_DRAWN),
        interval_values=choices(ACCESS_CYCLE_LENGTHS, k=ACCESS_CYCLES_DRAWN),
        connection_duration_values=choices(ACCESS_CYCLE_LENGTHS, k=ACCESS_CYCLES_DRAWN),
        connection_interval_values=choices(ACCESS_CYCLE_LENGTHS, k=ACCESS_CYCLES_DRAWN),
    )

    user.connection_to_application(application=app, access_model=access_model)
    return app


def create_link(
    node: ComponentManager,
    other: ComponentManager,
    delay: float = 1,
    bandwidth: int = NetworkLink.default_bandwidth,
    *,
    topology: Topology,
) -> NetworkLink:
    """Links two nodes of a topology with a static link.

    Args:
        node (ComponentManager): One end of the link.
        other (ComponentManager): The other end.
        delay (float): Delay of the link, in milliseconds.
        bandwidth (int): Bandwidth of the link.
        topology (Topology): The topology both nodes belong to.

    Returns:
        NetworkLink: The link, already in the topology.
    """
    link = NetworkLink()

    link["topology"] = topology
    link["nodes"] = [node, other]
    link["bandwidth"] = bandwidth
    link["delay"] = delay
    link["type"] = "static"

    topology.attach_link(link)
    return link


def get_satellites_from_api(
    coordinates: tuple[float, ...], sat_range: int, api_category: int = STARLINK_CATEGORY
) -> list[Sighting]:
    """Returns the satellites the N2YO API reports above a point, as the API describes them.

    Args:
        coordinates (tuple): The point, as (latitude, longitude) or (latitude, longitude, altitude).
        sat_range (int): Search radius, in degrees from the zenith, 0 to 90.
        api_category (int): N2YO category of the satellites.

    Returns:
        list: One sighting per satellite.

    Raises:
        ValueError: If the radius is out of range, the key is not set, or the API refuses the request.
        requests.RequestException: If the API cannot be reached or answers with an HTTP error.
    """
    if not 0 <= sat_range <= MAX_SEARCH_RADIUS:
        raise ValueError(
            f"Invalid search radius: {sat_range!r}. N2YO takes 0 to {MAX_SEARCH_RADIUS} degrees from the zenith."
        )

    key = os.environ.get(N2YO_KEY_VARIABLE)
    if not key:
        raise ValueError(f"{N2YO_KEY_VARIABLE} is not set; the N2YO API only answers requests that carry a key.")

    altitude = coordinates[ALTITUDE_INDEX] if len(coordinates) > ALTITUDE_INDEX else 0
    url = N2YO_ABOVE_URL.format(
        latitude=coordinates[0],
        longitude=coordinates[1],
        altitude=altitude,
        radius=sat_range,
        category=api_category,
        key=key,
    )
    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()

    answer = response.json()
    if "error" in answer:
        raise ValueError(f"The N2YO API refused the request: {answer['error']}")
    return answer.get("above", [])


def build_satellites(steps: list[list[Sighting]], max_satellites: int) -> None:
    """Creates the satellites a capture saw, each with its trace through the capture's steps.

    Every trace holds one slot per step. The slots of the steps before a satellite is first
    seen, and of the steps it is missing from, hold None, which `Satellite.step` fills from
    its mobility model.

    Args:
        steps (list): One list of N2YO satellite descriptions per step.
        max_satellites (int): How many satellites to create at most, first seen first taken.
    """
    satellites: dict[int, Satellite] = {}

    for index, step in enumerate(steps):
        for entry in step:
            satellite_id = entry["satid"]
            coordinates = (entry["satlat"], entry["satlng"], entry["satalt"])

            if satellite_id in satellites:
                satellites[satellite_id].coordinates_trace.append(coordinates)

            elif Satellite.count() < max_satellites:
                satellite = Satellite(
                    name=f"SATELLITE-{satellite_id}",
                    coordinates=coordinates,
                    max_connection_range=MAX_RANGE,
                    is_gateway=True,
                )
                satellite.coordinates_trace.extend([None] * index + [coordinates])
                satellites[satellite_id] = satellite

        for satellite in Satellite.all():
            if len(satellite.coordinates_trace) <= index:
                satellite.coordinates_trace.append(None)

    for satellite in Satellite.all():
        satellite.coordinates = satellite.coordinates_trace[0]


def stream_steps_from_api(
    max_steps: int = 10,
    interval: int = CAPTURE_INTERVAL_SECONDS,
    sat_range: int = MAX_SEARCH_RADIUS,
    api_category: int = STARLINK_CATEGORY,
) -> Iterator[list[Sighting]]:
    """Asks the N2YO API for the satellites above the reference point, `max_steps` times.

    Each capture is yielded as soon as the API answers, so a caller keeps what was captured
    before a failure.

    Args:
        max_steps (int): How many times to ask.
        interval (int): Seconds to wait between two captures.
        sat_range (int): Search radius, in degrees from the zenith.
        api_category (int): N2YO category of the satellites.

    Yields:
        list: The sightings of one capture, a step of a traces file.
    """
    for index in range(max_steps):
        if index:
            sleep(interval)
        yield get_satellites_from_api(REFERENCE_POINT, sat_range=sat_range, api_category=api_category)


def capture_steps_from_api(
    max_steps: int = 10,
    interval: int = CAPTURE_INTERVAL_SECONDS,
    sat_range: int = MAX_SEARCH_RADIUS,
    api_category: int = STARLINK_CATEGORY,
) -> list[list[Sighting]]:
    """Returns: list: Every capture `stream_steps_from_api` takes, in the format of a traces file."""
    return list(stream_steps_from_api(max_steps, interval, sat_range, api_category))


def load_satellites_from_api(
    max_steps: int = 10,
    interval: int = CAPTURE_INTERVAL_SECONDS,
    sat_range: int = MAX_SEARCH_RADIUS,
    api_category: int = STARLINK_CATEGORY,
    max_satellites: int = 100,
) -> None:
    """Creates the satellites the N2YO API reports above the reference point over `max_steps` captures."""
    build_satellites(capture_steps_from_api(max_steps, interval, sat_range, api_category), max_satellites)


def load_satellites_from_file(
    filename: str = "satellites.json", max_steps: int = 10, max_satellites: int = 100
) -> None:
    """Creates the satellites of a traces file, reading at most its first `max_steps` steps."""
    with open(filename, encoding="UTF-8") as file:
        steps = load(file)

    build_satellites(steps[:max_steps], max_satellites)


def create_satellite_topology(
    topology: Topology, filename: str, max_steps: int = 10, max_satellites: int = 100
) -> None:
    """Adds the satellites of a traces file to a topology and links those in range of each other.

    Args:
        topology (Topology): The topology to add them to.
        filename (str): The traces file.
        max_steps (int): How many of its steps to read.
        max_satellites (int): How many satellites to create at most.
    """
    load_satellites_from_file(filename=filename, max_steps=max_steps, max_satellites=max_satellites)

    topology.add_nodes_from(Satellite.all())

    mesh_network(topology)
