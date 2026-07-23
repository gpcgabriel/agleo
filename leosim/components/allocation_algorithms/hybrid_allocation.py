from ..process_unit import ProcessUnit
from ..satellite import Satellite
from ..user import User
from ..application import Application
from geopy.distance import geodesic
from math import sqrt
import networkx as nx


def has_path(topology, origin, target):
    for access_point in origin.network_access_points:
        if nx.has_path(G=topology, source=access_point, target=target):
            return True
    return False


def distance(coordinates1, coordinates2):
    if coordinates1 is None or coordinates2 is None:
        return float('inf')
    ground_distance = geodesic(coordinates1[:2], coordinates2[:2]).kilometers
    air_distance = (coordinates1[2] - coordinates2[2]) / 1000
    return sqrt(ground_distance**2 + air_distance**2)


def get_exposure_time(user, satellite):
    step = user.model.scheduler.steps
    max_distance = min(user.max_connection_range, satellite.max_connection_range)
    count = 0
    for coordinates in satellite.coordinates_trace[step:]:
        if coordinates is not None:
            if distance(coordinates1=coordinates, coordinates2=user.coordinates) < max_distance:
                count += 1
            else:
                break
    return count


def _get_eligible_pus(app, user, model, parameters):
    process_units = []
    for access_point in user.network_access_points:
        if isinstance(access_point, Satellite) and getattr(access_point, 'process_unit') is not None:
            pu = access_point.process_unit
            if pu.has_capacity_to_host(app) and pu.available:
                process_units.append(pu)

    if not process_units and parameters['ground_station'].process_unit:
        for unit in parameters['ground_station'].process_unit:
            if unit.has_capacity_to_host(app) and unit.available and has_path(model.topology, user, unit):
                process_units.append(unit)

    return process_units


def _load_ratio(pu):
    cpu_r = pu.cpu_demand / pu.cpu if pu.cpu > 0 else 1.0
    mem_r = pu.memory_demand / pu.memory if pu.memory > 0 else 1.0
    sto_r = pu.storage_demand / pu.storage if pu.storage > 0 else 1.0
    return cpu_r + mem_r + sto_r


def _allocate_single_app(app, user, model, parameters, strategy):
    if strategy == "best_fit":
        process_units = _get_eligible_pus(app, user, model, parameters)
        if not process_units:
            return "failed_no_capacity"
        target = min(process_units, key=lambda u:
                     (u.cpu - app.cpu_demand) + (u.memory - app.memory_demand) + (u.storage - app.storage_demand))
        if target != app.process_unit:
            app.provision(target)
            return "provisioned"
        return "already_provisioned"

    elif strategy == "longest_duration":
        best_target = None
        max_duration = -1
        scenario = parameters.get('scenario', 'hybrid')

        if parameters['ground_station'].process_unit and (scenario == 'terrestrial' or scenario == 'hybrid'):
            for unit in parameters['ground_station'].process_unit:
                if not isinstance(getattr(unit, 'owner', None), Satellite):
                    if unit.has_capacity_to_host(app) and unit.available:
                        if has_path(model.topology, user, unit):
                            best_target = unit
                            max_duration = float('inf')
                            break

        if best_target is None:
            for access_point in user.network_access_points:
                if not model.topology.has_node(access_point):
                    continue
                if isinstance(access_point, Satellite) and access_point.active:
                    pu = getattr(access_point, 'process_unit', None)
                    if pu and pu.available and pu.has_capacity_to_host(app):
                        duration = get_exposure_time(user, access_point)
                        if duration > max_duration:
                            max_duration = duration
                            best_target = pu

        if best_target is not None:
            if best_target != app.process_unit:
                app.provision(best_target)
                return "provisioned"
            return "already_provisioned"
        return "failed_no_capacity"

    elif strategy == "latency_aware":
        process_units = _get_eligible_pus(app, user, model, parameters)
        if not process_units:
            return "failed_no_capacity"
        user_coords = user.coordinates
        target = min(process_units, key=lambda pu: distance(user_coords, pu.coordinates) if pu.coordinates else float('inf'))
        if target != app.process_unit:
            app.provision(target)
            return "provisioned"
        return "already_provisioned"

    elif strategy == "load_balanced":
        process_units = _get_eligible_pus(app, user, model, parameters)
        if not process_units:
            return "failed_no_capacity"
        target = min(process_units, key=_load_ratio)
        if target != app.process_unit:
            app.provision(target)
            return "provisioned"
        return "already_provisioned"

    return "unknown_strategy"


def hybrid_allocation(model, parameters, best_fit_apps, longest_duration_apps, latency_aware_apps, load_balanced_apps):
    results = {"provisioned": 0, "failed": 0, "already": 0, "details": []}

    for app_id_list, strategy_name in [
        (best_fit_apps, "best_fit"),
        (longest_duration_apps, "longest_duration"),
        (latency_aware_apps, "latency_aware"),
        (load_balanced_apps, "load_balanced"),
    ]:
        for app_id in app_id_list:
            app = Application.find_by('id', app_id)
            if not app:
                continue
            user = app.user
            if not user:
                continue
            result = _allocate_single_app(app, user, model, parameters, strategy_name)
            results["details"].append({"app": app_id, "strategy": strategy_name, "result": result})
            if result == "provisioned":
                results["provisioned"] += 1
            elif result == "failed_no_capacity":
                results["failed"] += 1
            else:
                results["already"] += 1

    return results