import streamlit as st

def propose_run_simulation(steps: int) -> str:
    """
    Proposes to advance the simulation by a specific number of steps (ticks).
    
    Args:
        steps (int): Number of steps to advance.
    """
    st.session_state["pending_action"] = {
        "action": "run_simulation",
        "description": f"Advance simulation by {steps} steps",
        "parameters": {"steps": steps}
    }
    return f"Proposal registered: advance simulation by {steps} steps. Please confirm in the control panel."

def propose_add_process_unit(target_type: str, target_id: int, cpu: int, memory: int) -> str:
    """
    Proposes to add a new processing unit (ProcessUnit/Server) to a satellite or ground station.
    
    Args:
        target_type (str): Target node type ('Satellite' or 'GroundStation').
        target_id (int): ID of the target satellite or ground station.
        cpu (int): CPU capacity (e.g., 50 to 100).
        memory (int): Memory capacity (e.g., 50 to 100).
    """
    st.session_state["pending_action"] = {
        "action": "add_process_unit",
        "description": f"Add ProcessUnit (CPU={cpu}, Mem={memory}) to {target_type} {target_id}",
        "parameters": {
            "target_type": target_type,
            "target_id": target_id,
            "cpu": cpu,
            "memory": memory
        }
    }
    return f"Proposal registered: add ProcessUnit to {target_type} {target_id}. Please confirm in the control panel."

def propose_add_user(lat: float, lon: float, connection_range: int = 1500) -> str:
    """
    Proposes to create a new mobile user in the simulation.
    
    Args:
        lat (float): Initial user latitude.
        lon (float): Initial user longitude.
        connection_range (int): Maximum connection range in km.
    """
    st.session_state["pending_action"] = {
        "action": "add_user",
        "description": f"Create user at ({lat}, {lon}) with range of {connection_range}km",
        "parameters": {
            "lat": lat,
            "lon": lon,
            "connection_range": connection_range
        }
    }
    return f"Proposal registered: create new user at ({lat}, {lon}). Please confirm in the control panel."

def propose_add_app_to_user(user_id: int, cpu_demand: int, memory_demand: int) -> str:
    """
    Proposes to associate a new application with CPU and memory demands to a user.
    
    Args:
        user_id (int): ID of the target user.
        cpu_demand (int): CPU demand of the application.
        memory_demand (int): Memory demand of the application.
    """
    st.session_state["pending_action"] = {
        "action": "add_app_to_user",
        "description": f"Create application (CPU={cpu_demand}, Mem={memory_demand}) for User {user_id}",
        "parameters": {
                "cpu_demand": cpu_demand,
                "memory_demand": memory_demand,
                "user_id": user_id
            }
    }
    return f"Proposal registered: associate application with User {user_id}. Please confirm in the control panel."

def propose_restart_simulation(selected_gml: str = None, selected_json: str = None, num_users: int = None, num_satellites: int = None, scenario: str = None, algorithm: str = None) -> str:
    """
    Proposes to restart the simulation back to the initial step (Step 0) with the current or specified configurations.
    
    Args:
        selected_gml (str, optional): Path to terrestrial GML topology file.
        selected_json (str, optional): Path to satellite JSON file.
        num_users (int, optional): Number of users.
        num_satellites (int, optional): Maximum satellites.
        scenario (str, optional): Scenario ("hybrid", "leo", or "terrestrial").
        algorithm (str, optional): Allocation algorithm.
    """
    gml = selected_gml if selected_gml is not None else st.session_state.get("selected_gml_key")
    s_json = selected_json if selected_json is not None else st.session_state.get("selected_json_key")
    n_users = num_users if num_users is not None else st.session_state.get("num_users_key")
    n_sats = num_satellites if num_satellites is not None else st.session_state.get("num_satellites_key")
    scen = scenario if scenario is not None else st.session_state.get("scenario_key")
    alg = algorithm if algorithm is not None else st.session_state.get("algorithm_key")
    
    st.session_state["pending_action"] = {
        "action": "restart_simulation",
        "description": "Reset simulation back to Step 0",
        "parameters": {
            "selected_gml": gml,
            "selected_json": s_json,
            "num_users": n_users,
            "num_satellites": n_sats,
            "scenario": scen,
            "algorithm": alg
        }
    }
    return "Proposal registered: restart the simulation (reset to Step 0). Please confirm in the control panel."
