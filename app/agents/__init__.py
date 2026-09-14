"""LLM agents of the application.

Like `app/core`, no module here may import `streamlit`: the agent's tools
record proposals in a buffer, and the interface layer decides where to keep
them.
"""
