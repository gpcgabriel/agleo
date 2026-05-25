import os
from json import dump
from agno.agent import Agent
from agno.models.ollama import Ollama

def get_algorithms_code():
    code_context = ""
    path = "leosim/components/allocation_algorithms"
    files = ["best_fit_allocation.py", "longest_duration_allocation.py"]
    
    for file in files:
        full_path = os.path.join(path, file)
        if os.path.exists(full_path):
            with open(full_path, "r", encoding="utf-8") as f:
                code_context += f"\n--- SOURCE CODE FOR {file} ---\n{f.read()}\n"
    return code_context

def apply_offloading_strategy(strategy_name: str) -> str:
    """
    Applies a resource allocation heuristic to the satellite network.
    Args:
        strategy_name (str): Name of the heuristic ('best_fit_allocation' or 'longest_duration_allocation').
    """
    from leosim.component_manager import ComponentManager
    from leosim.components.allocation_algorithms import best_fit_allocation, longest_duration_allocation

    algorithms = {
        "best_fit_allocation": best_fit_allocation,
        "longest_duration_allocation": longest_duration_allocation
    }

    model = ComponentManager.model
    if not model:
        return "Error: Simulator model not initialized."

    selected_heuristic = algorithms.get(strategy_name)
    if selected_heuristic:
        selected_heuristic(model, model.resource_management_algorithm_parameters)
        return f"Successfully applied {strategy_name}."
    return f"Heuristic '{strategy_name}' not found."

offloading_agent = Agent(
    model=Ollama(id="qwen3.5", options={"temperature": 0}),
    tools=[apply_offloading_strategy],
    instructions=[
        "You are an expert Resource Management Controller for a LEO Satellite Network.",
        "Below is the source code for the heuristics you can use. READ THEM to understand their logic:",
        get_algorithms_code(),
        "1. Analyze the current network state provided (CPU, load, visibility).",
        "2. Choose the best algorithm based on the source code logic provided above.",
        "3. Call 'apply_offloading_strategy' with the chosen strategy_name.",
    ],
    markdown=True
)

def llm_orchestrator(model, parameters):
    from ..satellite import Satellite
    from ..ground_station import GroundStation
    from ..process_unit import ProcessUnit
    from ..application import Application
    from ..user import User

    current_state = f"""
    ### Current Simulation State
    - **Step**: {model.scheduler.steps}
    
    **Satellites:** {Satellite.export_satellites()}
    **Ground Stations:** {GroundStation.export_groundstations()}
    **Processing Units:** {ProcessUnit.export_processunits()}
    **Applications:** {Application.export_applications()}
    **Users:** {User.export_users()}
    """

    response = offloading_agent.run(
        f"Current State:\n{current_state}\n\nApply the best heuristic.",
        expected_output="The result of the tool call only."
    )

    output_data = {
        "step": model.scheduler.steps,
        "agent_response": response.to_dict()
    }
    
    with open("logs/agent_log.json", "w", encoding="utf-8") as json_file:
        dump(output_data, json_file, indent=4)

    print(response.content)