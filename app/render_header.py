import streamlit as st

from app.gui.icons import icon_satellite, wrap_icon


def render_header(is_dark: bool) -> None:
    """Render the main title and the light/dark theme toggle button."""
    col_title, col_toggle = st.columns([10, 2], vertical_alignment="center")
    with col_title:
        st.markdown(
            f"<h1>{wrap_icon(icon_satellite(26))} LEOSim - LEO Simulation Dashboard</h1>", unsafe_allow_html=True
        )
    with col_toggle:
        # Marker div so that sibling selector can target the button below
        st.markdown('<div class="theme-toggle-marker"></div>', unsafe_allow_html=True)
        btn_label = "☀️" if is_dark else "🌙"
        if st.button(btn_label, key="theme_toggle_btn", help="Toggle Light/Dark Theme"):
            st.session_state["is_dark"] = not is_dark
            st.rerun()
