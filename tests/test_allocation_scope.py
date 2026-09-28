"""Tests for narrowing an allocation question to one ground station.

`find_pending_app_ids` answers for the whole network. Without narrowing, every
station is asked about every pending application, so 28 stations produce 28
answers to the same global question and the localized decision the design is
built on does not exist. These assert the narrowing, on components built by
hand so no simulation clock has to advance.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.allocation.state import find_servable_app_ids, should_skip
from leosim.components import Application, GroundStation, Satellite, User
from leosim.components.application_access_models import FixedDurationAccessModel


def reset_components():
    for component_class in (Application, GroundStation, Satellite, User, FixedDurationAccessModel):
        component_class._instances = []
        component_class._object_count = 0


def make_user_with_application(access_points):
    """Builds a user owning one application, reachable through `access_points`."""
    user = User(coordinates=(0.0, 0.0, 0.0))
    application = Application()
    access_model = FixedDurationAccessModel()
    access_model.application = application
    access_model.user = user
    user.applications_access_models = [access_model]
    user.network_access_points = list(access_points)
    return user, application


def test_a_station_is_asked_about_users_on_the_satellites_it_reaches():
    reset_components()
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    satellite = Satellite(coordinates=(0.0, 0.0, 550.0))
    _, application = make_user_with_application([satellite])

    servable = find_servable_app_ids(station, [application.id], {satellite.id})

    assert servable == [application.id]


def test_a_station_is_not_asked_about_users_on_satellites_it_cannot_reach():
    reset_components()
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    far_satellite = Satellite(coordinates=(80.0, 80.0, 550.0))
    _, application = make_user_with_application([far_satellite])

    servable = find_servable_app_ids(station, [application.id], reachable_satellite_ids=set())

    assert servable == []


def test_a_station_is_asked_about_users_attached_to_it_directly():
    reset_components()
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    _, application = make_user_with_application([station])

    servable = find_servable_app_ids(station, [application.id], reachable_satellite_ids=set())

    assert servable == [application.id]


def test_a_disconnected_user_is_nobody_s_to_serve():
    reset_components()
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    satellite = Satellite(coordinates=(0.0, 0.0, 550.0))
    _, application = make_user_with_application([])

    servable = find_servable_app_ids(station, [application.id], {satellite.id})

    assert servable == []


def test_only_applications_still_pending_are_returned():
    """An application already placed is not pending, so it is not asked about."""
    reset_components()
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    satellite = Satellite(coordinates=(0.0, 0.0, 550.0))
    _, application = make_user_with_application([satellite])

    servable = find_servable_app_ids(station, pending_app_ids=[], reachable_satellite_ids={satellite.id})

    assert servable == []


def test_two_stations_reaching_different_users_get_different_questions():
    """This is the property the whole design rests on."""
    reset_components()
    north_station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    south_station = GroundStation(coordinates=(-30.0, -50.0, 0.0))
    north_satellite = Satellite(coordinates=(0.0, 0.0, 550.0))
    south_satellite = Satellite(coordinates=(-30.0, -50.0, 550.0))

    _, north_application = make_user_with_application([north_satellite])
    _, south_application = make_user_with_application([south_satellite])
    pending = [north_application.id, south_application.id]

    assert find_servable_app_ids(north_station, pending, {north_satellite.id}) == [north_application.id]
    assert find_servable_app_ids(south_station, pending, {south_satellite.id}) == [south_application.id]


def test_a_station_with_nothing_to_serve_skips():
    reset_components()
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    station.process_unit = []

    assert should_skip(station, [], set()) == "no servable pending apps"


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
