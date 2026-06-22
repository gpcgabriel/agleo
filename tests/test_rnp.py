import sys
import os

# Ensure project root is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
# Mock streamlit and streamlit_folium entirely before any import
from unittest.mock import MagicMock
mock_st = MagicMock()
mock_st.session_state = {}
# Configure sidebar methods to prevent triggering side effects during import
mock_st.sidebar.button.return_value = False
mock_st.sidebar.checkbox.return_value = False
mock_st.sidebar.selectbox.return_value = "datasets/rnp.gml"
mock_st.sidebar.number_input.return_value = 20

sys.modules['streamlit'] = mock_st
sys.modules['streamlit.components'] = MagicMock()
sys.modules['streamlit.components.v1'] = MagicMock()
sys.modules['streamlit_folium'] = MagicMock()

from app import initialize_simulation, serialize_state


def test_rnp():
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

    with capture_output("test_rnp"):
        print("Testing simulation initialization with rnp.gml and satellites_brazil.json...")
        dataset_gml = "datasets/rnp.gml"
        satellites_json = "datasets/satellites_brazil.json"
        
        sim = initialize_simulation(
            dataset_gml=dataset_gml,
            satellites_json=satellites_json,
            num_users=20,
            num_satellites=15,
            scenario="hybrid",
            algorithm="best_fit_allocation"
        )
        
        print("Simulator initialized successfully!")
        print(f"Initial steps: {sim.scheduler.steps}")
        
        # Check serialization
        snapshot = serialize_state(sim)
        print(f"Step {snapshot['step']} snapshot:")
        print(f"  Satellites: {len(snapshot['satellites'])}")
        print(f"  Ground Stations: {len(snapshot['ground_stations'])}")
        print(f"  Users: {len(snapshot['users'])}")
        print(f"  Links: {len(snapshot['links'])}")
        
        # Run a few steps
        for step in range(1, 4):
            print(f"Advancing to step {step}...")
            sim.step()
            snapshot = serialize_state(sim)
            print(f"Step {snapshot['step']} snapshot:")
            print(f"  Active Satellites: {len([s for s in snapshot['satellites'] if s['active']])}")
            print(f"  Connected Users: {len([u for u in snapshot['users'] if u['connected_aps']])}")
            print(f"  Links: {len(snapshot['links'])}")
        print("ALL TESTS PASSED!")

if __name__ == "__main__":
    test_rnp()
