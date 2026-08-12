import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock streamlit and streamlit_folium entirely before any import
from unittest.mock import MagicMock
mock_st = MagicMock()
mock_st.session_state = {
    "selected_gml_key": "datasets/rnp.gml",
    "selected_json_key": "datasets/satellites_brazil.json",
    "num_users_key": 20,
    "num_satellites_key": 15,
    "scenario_key": "hybrid",
    "algorithm_key": "best_fit_allocation",
    "pending_action": None
}
# Configure sidebar methods to prevent triggering side effects during import
mock_st.sidebar.button.return_value = False
mock_st.sidebar.checkbox.return_value = False
mock_st.sidebar.selectbox.return_value = "datasets/rnp.gml"
mock_st.sidebar.number_input.return_value = 20

sys.modules['streamlit'] = mock_st
sys.modules['streamlit.components'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()
sys.modules['streamlit_folium'] = MagicMock()

from app import (
    propose_run_simulation,
    propose_restart_simulation,
    propose_add_process_unit,
    propose_add_user,
    propose_add_app_to_user
)
from agno.agent import Agent
from agno.models.ollama import Ollama

def test_agent_commands():
    import io
    import sys
    from contextlib import contextmanager

    @contextmanager
    def capture_output(test_name):
        buffer = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = buffer
        sys.stderr = buffer
        try:
            yield buffer
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            print(f"=> {test_name}: SUCCESS")
        except Exception as e:
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            print(buffer.getvalue(), end="")
            raise e

    with capture_output("test_agent_commands"):
        print("Testing Agent Slash Commands...")
        
        # Enable tools
        tools = [
            propose_run_simulation,
            propose_restart_simulation,
            propose_add_process_unit,
            propose_add_user,
            propose_add_app_to_user
        ]
        
        agent = Agent(
            model=Ollama(id="llama3.1", options={"temperature": 0.1}),
            description=(
                "You are the LEOSim Dashboard Virtual Assistant, a simulator for LEO (Low Earth Orbit) satellite networks. "
                "You ALWAYS respond in natural language using formatted Markdown. "
                "NEVER return JSON, XML, code, or structured data objects as a response. "
                "Your responses must be textual, clear, and in English."
            ),
            tools=tools,
            instructions=[
                "CRITICAL FORMAT RULE: ALWAYS respond in natural prose with Markdown formatting. NEVER generate JSON, XML, code blocks, or data structures as your response. If you feel the urge to generate JSON, stop and rephrase as running text.",
                "Your task is to help the operator monitor, obtain information about, and control the LEO satellite network simulation.",
                "When receiving an informational question (e.g., 'how many applications are allocated?', 'what is user 3's lat/lon?', 'were there allocations on GS 28?'), respond clearly in natural language text based solely on the information provided in the context (Current Simulation State). DO NOT call tools to answer informational questions.",
                "You must only use proposal tools when the operator explicitly requests a change to the simulation.",
                "If the operator uses '/step <n>' (or variations like 'advance <n> steps'), call the 'propose_run_simulation' tool with steps=n.",
                "If the operator uses '/restart', call the 'propose_restart_simulation' tool.",
                "If the operator uses '/review' or '/review <region>', DO NOT call any tools. Perform a detailed textual analysis of the current topology using context data to identify issues like disconnected users, overloaded stations, missing servers, etc. Organize the analysis with Markdown headings and lists.",
                "Your tools DO NOT execute actions directly; they create a proposal (Confirmation Gate) that the user must confirm or cancel in the panel.",
                "If the operator asks to perform an action but tools are disabled, inform them they need to enable tools in the sidebar."
            ],
            markdown=True
        )
        
        # 1. Test /step 5
        prompt = "/step 5"
        print(f"\n--- Testing prompt: '{prompt}' ---")
        mock_st.session_state["pending_action"] = None
        context_state = "Quick Command Mode (Slash Command). Execute the corresponding action immediately by calling the appropriate tool."
        
        response = agent.run(f"{context_state}\n\nOperator Command: {prompt}")
        print("Agent Output:", response.content)
        print("Pending Action set in session state:", mock_st.session_state["pending_action"])
        assert mock_st.session_state["pending_action"] is not None
        assert mock_st.session_state["pending_action"]["action"] == "run_simulation"
        assert mock_st.session_state["pending_action"]["parameters"]["steps"] == 5
        print("=> /step 5 passed!")
        
        # 2. Test /restart
        prompt = "/restart"
        print(f"\n--- Testing prompt: '{prompt}' ---")
        mock_st.session_state["pending_action"] = None
        response = agent.run(f"{context_state}\n\nOperator Command: {prompt}")
        print("Agent Output:", response.content)
        print("Pending Action set in session state:", mock_st.session_state["pending_action"])
        assert mock_st.session_state["pending_action"] is not None
        assert mock_st.session_state["pending_action"]["action"] == "restart_simulation"
        assert mock_st.session_state["pending_action"]["parameters"]["scenario"] == "hybrid"
        print("=> /restart passed!")

        # 3. Test /review
        prompt = "/review"
        print(f"\n--- Testing prompt: '{prompt}' ---")
        mock_st.session_state["pending_action"] = None
        detailed_context = "You have access to the current detailed simulation state below:\n\n[SIMULATION STATE] User 1 is disconnected. Ground Station 28 has 0 servers.\n\nUse this data to answer."
        response = agent.run(f"{detailed_context}\n\nOperator Command: {prompt}")
        print("Agent Output:", response.content)
        print("Pending Action set in session state (should be None):", mock_st.session_state["pending_action"])
        assert mock_st.session_state["pending_action"] is None
        assert "disconnected" in response.content.lower() or "user 1" in response.content.lower()
        print("=> /review passed!")

if __name__ == "__main__":
    test_agent_commands()
