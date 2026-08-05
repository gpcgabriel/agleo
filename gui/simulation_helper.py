from json import load
import streamlit as st
import random
import dataset as ds
from leosim import ComponentManager, Simulator, default_topology_management
from leosim.components import Satellite
from geopy.distance import geodesic

def get_coordinates_trace(id_reference, coords):
        with open("datasets/satellites_brazil.json", 'r', encoding='UTF-8') as file:
                data = load(file)

        coords_trace = [coords]
        flag = False

        for list_sats in data:
                for sat in list_sats:
                        if flag and sat['satid'] == id_reference:
                                coords_trace.extend([(sat['satlat'], sat['satlng'], sat['satalt'])])
                                break
                        
                        if coords[0] == sat['satlat'] and coords[1] == sat['satlng'] and coords[2] == sat['satalt']:
                                flag = True

        return coords_trace

def id_not_in_satellites_list(id) -> bool:
        for sat in Satellite.all():
                if id == sat.id:
                        return False
        return True

def get_closest_satellite(target_coord):
    target_lat_lon = (target_coord[0], target_coord[1])
    
    with open('datasets/satellites_brazil.json', 'r') as file:
        satellites = load(file)
        
    closest_satid = None
    closest_coords = None
    min_distance = float('inf')
    
    for list_sats in satellites:
        for sat in list_sats:
                sat_lat_lon = (sat['satlat'], sat['satlng'])
                distance = geodesic(target_lat_lon, sat_lat_lon).kilometers

                if distance < min_distance and sat['satid'] not in [s.id for s in Satellite.all()]:
                        min_distance = distance
                        closest_satid = sat['satid']
                        closest_coords = (sat['satlat'], sat['satlng'], sat['satalt'])
            
    return closest_satid, closest_coords

def serialize_state(sim):
    """
    Serializes the simulator's current state into a JSON-compatible dictionary.
    """
    from leosim.components import Satellite, GroundStation, User
    state = {
        "step": sim.scheduler.steps,
        "satellites": [],
        "ground_stations": [],
        "users": [],
        "links": []
    }
    
    # Export satellites
    for sat in Satellite.all():
        if sat.coordinates:
            state["satellites"].append({
                "id": sat.id,
                "name": sat.name,
                "lat": sat.coordinates[0],
                "lon": sat.coordinates[1],
                "alt": sat.coordinates[2],
                "is_gateway": sat.is_gateway,
                "active": sat.active,
                "max_connection_range": sat.max_connection_range,
                "process_unit": {
                    "id": sat.process_unit.id,
                    "cpu": sat.process_unit.cpu,
                    "memory": sat.process_unit.memory,
                    "storage": sat.process_unit.storage
                } if sat.process_unit else None
            })
            
    # Export ground stations
    for gs in GroundStation.all():
        if gs.coordinates:
            state["ground_stations"].append({
                "id": gs.id,
                "lat": gs.coordinates[0],
                "lon": gs.coordinates[1],
                "alt": gs.coordinates[2] if len(gs.coordinates) > 2 else 0,
                "max_connection_range": gs.max_connection_range,
                "wireless_delay": gs.wireless_delay,
                "process_units": [{
                    "id": pu.id,
                    "cpu": pu.cpu,
                    "memory": pu.memory,
                    "storage": pu.storage
                } for pu in gs.process_unit] if gs.process_unit else []
            })
            
    # Export users
    for user in User.all():
        if user.coordinates:
            state["users"].append({
                "id": user.id,
                "lat": user.coordinates[0],
                "lon": user.coordinates[1],
                "alt": user.coordinates[2] if len(user.coordinates) > 2 else 0,
                "max_connection_range": user.max_connection_range,
                "connected_aps": [{
                    "id": ap.id,
                    "class": type(ap).__name__
                } for ap in user.network_access_points] if getattr(user, 'network_access_points', None) else [],
                "applications": [{
                    "id": app.id,
                    "cpu_demand": app.cpu_demand,
                    "memory_demand": app.memory_demand,
                    "storage_demand": app.storage_demand,
                    "allocated_to": app.process_unit.id if getattr(app, 'process_unit', None) else None
                } for app in user.applications]
            })
            
    # Export links
    for u, v, data in sim.topology.edges(data=True):
        if hasattr(u, 'coordinates') and hasattr(v, 'coordinates') and u.coordinates and v.coordinates:
            state["links"].append({
                "source": {
                    "id": u.id,
                    "class": type(u).__name__,
                    "lat": u.coordinates[0],
                    "lon": u.coordinates[1]
                },
                "target": {
                    "id": v.id,
                    "class": type(v).__name__,
                    "lat": v.coordinates[0],
                    "lon": v.coordinates[1]
                },
                "delay": data.get('delay', 0),
                "bandwidth": data.get('bandwidth', 0),
                "type": data.get('type', 'static')
            })
            
    return state

def get_simulation_state_summary(snapshot):
    """
    Formats the state snapshot into a markdown text summary for the AI agent context.
    """
    summary = []
    summary.append(f"### Simulation State Information (Current Step: {snapshot['step']})")
    
    # Satellites summary
    summary.append("\n🛰️ Satellites in Constellation:")
    active_sats = [s for s in snapshot["satellites"] if s["active"]]
    if active_sats:
        for sat in active_sats:
            pu_info = "No CPU/Memory (no processing)"
            if sat["process_unit"]:
                pu = sat["process_unit"]
                pu_info = f"ProcessUnit {pu['id']} (CPU Capacity: {pu['cpu']}, Memory: {pu['memory']})"
            summary.append(f"  - {sat['name']} (ID: {sat['id']}): Lat/Lon: {sat['lat']:.4f}, {sat['lon']:.4f}. {pu_info}")
    else:
        summary.append("  No active satellites at the moment.")
        
    # Ground Stations summary
    summary.append("\n🏠 Ground Stations:")
    if snapshot["ground_stations"]:
        for gs in snapshot["ground_stations"]:
            pu_details = []
            for pu in gs["process_units"]:
                pu_details.append(f"Server/ProcessUnit {pu['id']} (CPU: {pu['cpu']}, Mem: {pu['memory']})")
            pu_info = ", ".join(pu_details) if pu_details else "No processing unit (no server)"
            summary.append(f"  - GroundStation {gs['id']}: Lat/Lon: {gs['lat']:.4f}, {gs['lon']:.4f}. Servers: [{pu_info}]")
    else:
        summary.append("  No ground stations registered.")
        
    # Users & Applications allocation summary
    summary.append("\n👥 Users & Application Demands:")
    if snapshot["users"]:
        for u in snapshot["users"]:
            connected_aps_desc = []
            for ap in u["connected_aps"]:
                connected_aps_desc.append(f"{ap['class']} {ap['id']}")
            conn_status = f"Connected to: {', '.join(connected_aps_desc)}" if connected_aps_desc else "Disconnected (no signal)"
            
            app_details = []
            for app in u["applications"]:
                if app['allocated_to'] is not None:
                    alloc = f"ALLOCATED/HOSTED on Server/ProcessUnit ID {app['allocated_to']}"
                else:
                    alloc = f"NOT ALLOCATED (waiting for resources)"
                app_details.append(f"App ID {app['id']} [CPU Req: {app['cpu_demand']}, Mem Req: {app['memory_demand']} - Status: {alloc}]")
            app_info = " | ".join(app_details) if app_details else "No active applications"
            
            summary.append(f"  - User ID {u['id']}: Lat/Lon: {u['lat']:.4f}, {u['lon']:.4f} | Status: {conn_status} | Applications: {app_info}")
    else:
        summary.append("  No active users in the simulation.")
        
    # Links
    summary.append(f"\n🔗 Active Network Connections: {len(snapshot['links'])}")
    
    return "\n".join(summary)

def initialize_simulation(dataset_gml, satellites_json, num_users, num_satellites, scenario, algorithm):
    """
    Configures and initializes the LEO simulator from topology files.
    """
    from leosim.components.allocation_algorithms import best_fit_allocation, longest_duration_allocation
    
    # Clear previous simulator components
    for cls in ComponentManager.__subclasses__():
        if cls.__name__ != "Simulator":
            cls.clear()
            
    # Set seed for repeatability
    random.seed(42)
    
    # Load topology
    t = ds.load_topology(
        ground_topology=dataset_gml,
        leo_topology=satellites_json,
        max_satellites=num_satellites
    )
    
    # Create users
    ds.create_users(num_users)
    
    total_resources = Satellite.count()
    
    # Add process units
    if scenario == "terrestrial":
        ds.add_process_unit_to_ground_stations(t, num_process_units=total_resources)
    elif scenario == "leo":
        ds.add_process_unit_to_satellites(t, num_process_units=total_resources)
    elif scenario == "hybrid":
        ds.add_process_unit_to_ground_stations(t, num_process_units=total_resources)
        ds.add_process_unit_to_satellites(t, num_process_units=total_resources)
        
    # Configure mobility models
    ds.configure_mobility_models()
    
    # Save configuration to temporary file
    temp_file = "datasets/temp_dashboard_scenary.json"
    ComponentManager.save_scenary(filename=temp_file)
    
    # Map resource management algorithm
    algorithms = {
        "best_fit_allocation": best_fit_allocation,
        "longest_duration_allocation": longest_duration_allocation
    }
    selected_alg = algorithms[algorithm]
    
    # Create Simulator
    sim = Simulator(
        stopping_criterion=lambda model: False,
        resource_management_algorithm=selected_alg,
        topology_management_algorithm=default_topology_management,
        clean_data_in_memory=True,
        logs_directory="logs/dashboard"
    )
    sim.initialize(temp_file)
    return sim

def execute_pending_action():
    """
    Executes the current proposed action set in Streamlit session state.
    """
    pending = st.session_state["pending_action"]
    if not pending:
        return
        
    sim = st.session_state["simulator"]
    action = pending["action"]
    params = pending["parameters"]
    
    spinner_msg = f"⚙️ Running Network Simulation: {pending['description']}..." if action == "run_simulation" else f"🔧 Applying physical network change: {pending['description']}..."
    with st.spinner(spinner_msg):
        if action == "run_simulation":
            steps = params["steps"]
            st.session_state["steps_remaining"] = steps
            st.session_state["pending_action"] = None
            
        elif action == "restart_simulation":
            sim = initialize_simulation(
                params["selected_gml"],
                params["selected_json"],
                params["num_users"],
                params["num_satellites"],
                params["scenario"],
                params["algorithm"]
            )
            st.session_state["simulator"] = sim
            initial_snapshot = serialize_state(sim)
            st.session_state["simulation_history"] = [initial_snapshot]
            st.session_state["current_step_index"] = 0
            
            st.session_state["chat_messages"].append({
                "role": "system",
                "content": f"Action executed successfully: {pending['description']}"
            })
            st.session_state["success_banner"] = f"Action executed successfully: {pending['description']}"
            st.session_state["toast_message"] = f"Action completed: {pending['description']}"
            st.session_state["pending_action"] = None
            
        elif action == "add_process_unit":
            from leosim.components import ProcessUnit, Satellite, GroundStation, NetworkLink
            from dataset_generator.create_components import create_link

            for param in params:
                target_type = param["target_type"]
                target_id = param["target_id"] if "target_id" in param else None
                reference_coordinates = param["reference_coordinates"] if "reference_coordinates" in param else None
                cpu = param["cpu"]
                memory = param["memory"]
                
                unit = ProcessUnit(cpu=cpu, memory=memory, storage=memory)
                
                if target_type == "Satellite":
                    satellite = Satellite.find_by("id", target_id) if target_id is not None else None
                    if not satellite:
                        id_reference, coords = get_closest_satellite(reference_coordinates)
                        trace = [coords]
                        if id_not_in_satellites_list(id_reference):
                            trace = get_coordinates_trace(id_reference, coords)

                        satellite = Satellite(id=id_reference, name=f"SATELLITE-{id_reference}", coordinates=reference_coordinates, is_gateway=True)
                        satellite.active = True
                        satellite.coordinates_trace = trace
                        sim.topology.add_node(satellite)
                    
                    unit.coordinates = satellite.coordinates
                    create_link(unit, satellite, 1, bandwidth=NetworkLink.default_bandwidth, topology=sim.topology)
                    satellite.process_unit = unit
                    sim.topology.add_node(unit)

                else:
                    station = GroundStation.find_by("id", target_id)
                    
                    if not station:
                        station = GroundStation(coordinates=reference_coordinates)

                    unit.coordinates = station.coordinates
                    create_link(unit, station, 10, bandwidth=NetworkLink.default_bandwidth, topology=sim.topology)
                    station.connect_server(unit)
                    sim.topology.add_node(unit)
                    
            sim.step()
            snapshot = serialize_state(sim)
            st.session_state["simulation_history"].append(snapshot)
            st.session_state["current_step_index"] = len(st.session_state["simulation_history"]) - 1
            
            st.session_state["chat_messages"].append({
                "role": "system",
                "content": f"Action executed successfully: {pending['description']}"
            })
            st.session_state["success_banner"] = f"Action executed successfully: {pending['description']}"
            st.session_state["toast_message"] = f"Action completed: {pending['description']}"
            st.session_state["pending_action"] = None
            
        elif action == "add_user":
            from dataset_generator.create_components import create_user
            lat = params["lat"]
            lon = params["lon"]
            connection_range = params["connection_range"]
            
            user = create_user((lat, lon, 0), connection_range)
            # Function to move user (static for now, can be updated if needed)
            user.mobility_model = lambda u: u.coordinates_trace.append(u.coordinates)
            
            sim.step()
            snapshot = serialize_state(sim)
            st.session_state["simulation_history"].append(snapshot)
            st.session_state["current_step_index"] = len(st.session_state["simulation_history"]) - 1
            
            st.session_state["chat_messages"].append({
                "role": "system",
                "content": f"Action executed successfully: {pending['description']}"
            })
            st.session_state["success_banner"] = f"Action executed successfully: {pending['description']}"
            st.session_state["toast_message"] = f"Action completed: {pending['description']}"
            st.session_state["pending_action"] = None
            
        elif action == "add_app_to_user":
            from dataset_generator.create_components import create_application_to_user
            from leosim.components import User
            user_id = params["user_id"]
            cpu_demand = params["cpu_demand"]
            memory_demand = params["memory_demand"]
            
            user = User.find_by("id", user_id)
            if user:
                create_application_to_user(user, cpu_demand, memory_demand)
                
            sim.step()
            snapshot = serialize_state(sim)
            st.session_state["simulation_history"].append(snapshot)
            st.session_state["current_step_index"] = len(st.session_state["simulation_history"]) - 1
            
            st.session_state["chat_messages"].append({
                "role": "system",
                "content": f"Action executed successfully: {pending['description']}"
            })
            st.session_state["success_banner"] = f"Action executed successfully: {pending['description']}"
            st.session_state["toast_message"] = f"Action completed: {pending['description']}"
            st.session_state["pending_action"] = None
