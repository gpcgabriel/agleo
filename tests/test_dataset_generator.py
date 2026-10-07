"""Tests for the scenario builders in `dataset_generator`.

The N2YO API is never reached: `requests.get` is replaced by a response built here, and the
key the code reads from the environment is a placeholder set for the test alone.
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataset_generator import (
    build_satellites,
    capture_steps_from_api,
    create_application_to_user,
    create_user,
    get_satellites_from_api,
    load_satellites_from_api,
    load_satellites_from_file,
)
from dataset_generator.create_components import N2YO_KEY_VARIABLE, REFERENCE_POINT
from leosim import clear_components
from leosim.components import DynamicDurationAccessModel, Satellite

TEST_KEY = "test-key"


def seen(satellite_id: int, latitude: float) -> dict:
    """Returns: dict: One satellite as the N2YO "above" endpoint describes it."""
    return {
        "satid": satellite_id,
        "satname": f"STARLINK-{satellite_id}",
        "satlat": latitude,
        "satlng": -47.0,
        "satalt": 550.0,
    }


def answering(payload: dict) -> MagicMock:
    """Returns: MagicMock: A response from the API carrying the given payload."""
    response = MagicMock()
    response.json.return_value = payload
    return response


# -- Asking the API ----------------------------------------------------------


def test_the_api_is_asked_with_the_key_from_the_environment():
    with (
        patch.dict(os.environ, {N2YO_KEY_VARIABLE: TEST_KEY}),
        patch("requests.get", return_value=answering({"above": [seen(1, -15.0)]})) as get,
    ):
        satellites = get_satellites_from_api((-15.6, -48.0, 0), sat_range=70)

    assert satellites == [seen(1, -15.0)]
    url = get.call_args.args[0]
    assert url.endswith(f"/-15.6/-48.0/0/70/52/&apiKey={TEST_KEY}")
    assert get.call_args.kwargs["timeout"] > 0


def test_a_missing_key_is_refused_before_any_request():
    with patch.dict(os.environ), patch("requests.get") as get:
        os.environ.pop(N2YO_KEY_VARIABLE, None)
        try:
            get_satellites_from_api((-15.6, -48.0), sat_range=70)
        except ValueError as error:
            assert N2YO_KEY_VARIABLE in str(error)
        else:
            raise AssertionError("a request without a key was attempted")

    get.assert_not_called()


def test_an_error_the_api_reports_is_raised_instead_of_reading_as_no_satellites():
    with (
        patch.dict(os.environ, {N2YO_KEY_VARIABLE: TEST_KEY}),
        patch("requests.get", return_value=answering({"error": "Invalid API Key!"})),
    ):
        try:
            get_satellites_from_api((-15.6, -48.0), sat_range=70)
        except ValueError as error:
            assert "Invalid API Key!" in str(error)
        else:
            raise AssertionError("an error answer was read as an empty sky")


def test_an_http_error_is_raised():
    response = answering({})
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")

    with patch.dict(os.environ, {N2YO_KEY_VARIABLE: TEST_KEY}), patch("requests.get", return_value=response):
        try:
            get_satellites_from_api((-15.6, -48.0), sat_range=70)
        except requests.exceptions.HTTPError as error:
            assert "429" in str(error)
        else:
            raise AssertionError("an HTTP error was swallowed")


# -- Building satellites from a capture ----------------------------------------------


def test_a_satellite_first_seen_later_starts_with_empty_slots():
    """Its trace lines up with the steps: one empty slot per step before it was first seen."""
    clear_components()
    build_satellites([[seen(1, -10.0)], [seen(1, -11.0), seen(2, -20.0)]], max_satellites=10)

    first, second = Satellite.all()
    assert first.coordinates_trace == [(-10.0, -47.0, 550.0), (-11.0, -47.0, 550.0)]
    assert first.coordinates == (-10.0, -47.0, 550.0)
    assert second.coordinates_trace == [None, (-20.0, -47.0, 550.0)]
    assert second.coordinates is None


def test_a_satellite_missing_from_a_step_keeps_an_empty_slot_for_it():
    """The positions measured after the gap stay at the steps they were measured in."""
    clear_components()
    build_satellites([[seen(1, -10.0)], [], [seen(1, -12.0)], [seen(1, -13.0)]], max_satellites=10)

    assert Satellite.all()[0].coordinates_trace == [
        (-10.0, -47.0, 550.0),
        None,
        (-12.0, -47.0, 550.0),
        (-13.0, -47.0, 550.0),
    ]


def test_every_trace_holds_one_slot_per_step():
    clear_components()
    build_satellites([[seen(1, -10.0)], [seen(2, -20.0)], []], max_satellites=10)

    assert [len(satellite.coordinates_trace) for satellite in Satellite.all()] == [3, 3]


def test_the_first_satellites_seen_are_the_ones_kept():
    clear_components()
    build_satellites([[seen(1, -10.0), seen(2, -11.0), seen(3, -12.0)]], max_satellites=2)

    assert [satellite.name for satellite in Satellite.all()] == ["SATELLITE-1", "SATELLITE-2"]


def test_a_traces_file_is_read_up_to_the_steps_asked_for():
    steps = [[seen(1, -10.0 - index)] for index in range(5)]

    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "traces.json")
        with open(path, "w", encoding="UTF-8") as file:
            json.dump(steps, file)

        clear_components()
        load_satellites_from_file(path, max_steps=3, max_satellites=10)

    assert len(Satellite.all()[0].coordinates_trace) == 3


def test_a_capture_asks_once_per_step_and_waits_after_each_answer():
    steps = [[seen(1, -10.0)], [seen(1, -11.0), seen(2, -20.0)]]

    with (
        patch("dataset_generator.create_components.get_satellites_from_api", side_effect=steps) as ask,
        patch("dataset_generator.create_components.sleep") as wait,
    ):
        captured = capture_steps_from_api(max_steps=2, interval=30)

    assert captured == steps
    assert [call.args[0] for call in ask.call_args_list] == [REFERENCE_POINT, REFERENCE_POINT]
    assert [call.args for call in wait.call_args_list] == [(30,), (30,)]


def test_a_capture_from_the_api_builds_the_same_satellites_as_a_file_would():
    steps = [[seen(1, -10.0)], [seen(1, -11.0), seen(2, -20.0)]]

    with (
        patch("dataset_generator.create_components.get_satellites_from_api", side_effect=steps),
        patch("dataset_generator.create_components.sleep"),
    ):
        clear_components()
        load_satellites_from_api(max_steps=2, interval=0, max_satellites=10)
    captured = [satellite.coordinates_trace for satellite in Satellite.all()]

    clear_components()
    build_satellites(steps, max_satellites=10)

    assert captured == [satellite.coordinates_trace for satellite in Satellite.all()]


# -- Applications ----------------------------------------------------------------


def test_an_application_uses_the_access_model_asked_for():
    clear_components()
    user = create_user((-15.0, -47.0, 0))

    application = create_application_to_user(user, 10, 10, access_class=DynamicDurationAccessModel)

    assert isinstance(user.applications_access_models[0], DynamicDurationAccessModel)
    assert user.applications == [application]


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
