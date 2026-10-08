"""Tests for how the access models schedule a user's requests and keep a flow open.

Both models share the schedule; they differ in when an access ends, fixed by
its duration or once the application has been provisioned for that long.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from leosim import Simulator, clear_components
from leosim.components import (
    Application,
    DynamicDurationAccessModel,
    FixedDurationAccessModel,
    GroundStation,
    NetworkLink,
    ProcessUnit,
    User,
)

# Scheduling one access of 6 steps from step 1, in bursts of 2 requests with 1 idle step between them.
SCHEDULE = {"duration_values": [6], "interval_values": [2], "connection_duration_values": [2]}


def make_user() -> tuple[Simulator, User, Application]:
    """Returns: tuple: The simulator, a user reaching a station that hosts the application's unit."""
    clear_components()
    simulator = Simulator()
    station = GroundStation(coordinates=(0.0, 0.0, 0.0))
    unit = ProcessUnit(cpu=10, memory=10, storage=10)
    link = NetworkLink()
    link["nodes"] = [station, unit]
    simulator.topology.attach_link(link)
    user = User(coordinates=(0.0, 0.0, 0.0))
    user.network_access_points = [station]
    application = Application()
    application.process_unit = unit
    return simulator, user, application


def test_an_access_requests_in_bursts_separated_by_idle_steps() -> None:
    _simulator, user, application = make_user()

    access_model = FixedDurationAccessModel(user, application, 1, connection_interval_values=[1], **SCHEDULE)

    assert access_model.history == [
        {
            "start": 1,
            "end": 7,
            "provisioned_time": 0,
            "is_provisioned": False,
            "waiting_provisioning": 0,
            "access_time": 0,
            "connection_failure_time": 0,
            "making_request": {"1": True, "2": True, "4": True, "5": True},
            "next_access": 9,
        }
    ]


def test_a_dynamic_access_waits_for_its_provisioned_time_to_end() -> None:
    simulator, user, application = make_user()
    access_model = DynamicDurationAccessModel(user, application, 1, connection_interval_values=[1], **SCHEDULE)
    current_access = access_model.history[-1]
    assert (current_access["end"], current_access["required_provisioning_time"]) == (None, 6)

    application.available = True
    current_access["provisioned_time"] = 7
    simulator.scheduler.steps = 9
    access_model.update_access()

    assert current_access["end"] == 10


def test_a_request_step_opens_a_flow_from_the_users_access_point() -> None:
    simulator, user, application = make_user()
    access_model = FixedDurationAccessModel(user, application, 1, connection_interval_values=[1], **SCHEDULE)
    simulator.scheduler.steps = 1

    access_model.update_access()

    assert access_model.flow is not None
    assert access_model.flow.path == [user.network_access_points[0], application.process_unit]
    assert access_model.flow.start == 2


def test_an_idle_step_opens_no_flow() -> None:
    simulator, user, application = make_user()
    access_model = FixedDurationAccessModel(user, application, 1, connection_interval_values=[1], **SCHEDULE)
    simulator.scheduler.steps = 3

    access_model.update_access()

    assert access_model.flow is None


def test_an_access_model_with_no_idle_time_between_bursts_is_refused() -> None:
    _simulator, user, application = make_user()

    try:
        DynamicDurationAccessModel(user, application, 1, connection_interval_values=[], **SCHEDULE)
    except ValueError as error:
        assert "connection interval" in str(error)
    else:
        raise AssertionError("a schedule with no idle time between bursts was accepted")


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
