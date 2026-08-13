# Importing agno modules
from agno.agent import Agent
from agno.models.ollama import Ollama
from agno.skills import Skills, LocalSkills

# Importing internal modules
from dashboard_agent.agent_tools import *
from dashboard_agent.prompts import *


def instantiate_agent(selected_model, action_mode):
    """ """
    model = Ollama(
        id=selected_model,
        options={"temperature": 0.1},
    )

    if action_mode == "Tools":
        tools = [
            propose_run_simulation,
            propose_restart_simulation,
            propose_add_process_unit,
            propose_add_user,
            propose_add_app_to_user,
            propose_add_node,
        ]

        agent = Agent(
            model=model,
            description=dashboard_agent_description,
            tools=tools,
            instructions=dashbord_agent_instructions,
        )
        return agent

    elif action_mode == "Skills":
        skills = Skills(
            local_skills=LocalSkills(),
        )
        return Agent(
            model=model,
            description=dashboard_agent_description,
            skills=skills,
            instructions=dashbord_agent_instructions,
        )
    else:
        raise ValueError("Invalid action mode. Must be 'Tools' or 'Skills'.")


def run_agent(prompt, selected_model, action_mode, context_state):
    """ """
    agent = instantiate_agent(selected_model, action_mode)
    response = agent.run(f"Context state: {context_state}\n\nOperator Command: {prompt}")
    return response
