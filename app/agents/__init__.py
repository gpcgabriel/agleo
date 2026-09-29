"""LLM agents of the application, one package each.

* `allocation/` — the ground station agent, injected into the engine as an
  ordinary allocation algorithm.
* `dashboard/` — the agent the operator talks to, which proposes typed actions
  behind a confirmation gate.

Like `app/core`, no module here may import `streamlit`: an agent's tools record
proposals in a buffer, and the interface layer decides where to keep them.
"""
