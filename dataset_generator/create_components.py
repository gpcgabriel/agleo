"""Builders for the components of a scenario: users, applications, links and satellites.

Satellites come from a capture of the N2YO "above" endpoint: a list of steps, each the list
of satellites the API reported above a point at that moment. A traces file such as
`datasets/satellites_brazil.json` holds one, and `capture_steps_from_api` takes a new one.
"""

import os
from json import load
from random import choices
from time import sleep

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
from leosim.geometry import ALTITUDE_INDEX

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


def create_user(coordinates: tuple, connection_range: int = MAX_RANGE) -> User:
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

    topology.add_edge(node, other)

    topology._adj[node][other] = link
    topology._adj[other][node] = link
    return link


def get_satellites_from_api(coordinates: tuple, sat_range: int, api_category: int = 52) -> list[dict]:
    """Returns the satellites the N2YO API reports above a point, as the API describes them.

    Args:
        coordinates (tuple): The point, as (latitude, longitude) or (latitude, longitude, altitude).
        sat_range (int): Search radius, in degrees, as the API takes it.
        api_category (int): N2YO category of the satellites, 52 being Starlink.

    Returns:
        list: One dictionary per satellite, carrying "satid", "satlat", "satlng" and "satalt".

    Raises:
        ValueError: If the key is not set, or if the API refuses the request.
        requests.RequestException: If the API cannot be reached or answers with an HTTP error.
    """
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


def build_satellites(steps: list[list[dict]], max_satellites: int) -> None:
    """Creates the satellites a capture saw, each with its trace through the capture's steps.

    A satellite joins the trace at the step it is first seen. The slots of earlier steps, and
    of steps it is missing from, hold None, which `Satellite.step` fills from its mobility
    model.

    Args:
        steps (list): One list of N2YO satellite descriptions per step.
        max_satellites (int): How many satellites to create at most, first seen first taken.
    """
    satellites = {}

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
            if len(satellite.coordinates_trace) < index:
                satellite.coordinates_trace.append(None)

    for satellite in Satellite.all():
        satellite.coordinates = satellite.coordinates_trace[0]


def capture_steps_from_api(
    max_steps: int = 10, interval: int = 30, sat_range: int = 1000, api_category: int = 52
) -> list[list[dict]]:
    """Asks the N2YO API for the satellites above the reference point, `max_steps` times.

    Args:
        max_steps (int): How many times to ask.
        interval (int): Seconds to wait after each answer.
        sat_range (int): Search radius, in degrees.
        api_category (int): N2YO category of the satellites.

    Returns:
        list: One list of satellite descriptions per step, in the format of a traces file.
    """
    steps = []
    for _ in range(max_steps):
        steps.append(get_satellites_from_api(REFERENCE_POINT, sat_range=sat_range, api_category=api_category))
        sleep(interval)
    return steps


def load_satellites_from_api(
    max_steps: int = 10, interval: int = 30, sat_range: int = 1000, api_category: int = 52, max_satellites: int = 100
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
