"""LEOSim application.

This package deliberately re-exports nothing: importing `app` (or anything
under `app.core` / `app.agents`) must not pull Streamlit in. The interface
modules live in `app/ui` and are imported explicitly by the `app.py` entry
point.
"""
