import streamlit as st

from app.ui.gui.icons import icon_satellite, wrap_icon


def render_header(is_dark: bool, toggle_disabled: bool = False) -> None:
    """Render the main title and the light/dark theme toggle button.

    Args:
        is_dark (bool): Whether the dark theme is on.
        toggle_disabled (bool): Whether the toggle is locked. Streamlit
            stops the running script on any widget interaction, so a
            toggle pressed while the agent is answering would throw the
            answer away.
    """
    col_title, col_toggle = st.columns([10, 2], vertical_alignment="center")
    with col_title:
        st.markdown(
            f"<h1>{wrap_icon(icon_satellite(26))} LEOSim - LEO Simulation Dashboard</h1>", unsafe_allow_html=True
        )
    with col_toggle:
        # Marking the block so the sibling selector can reach the button below.
        st.markdown('<div class="theme-toggle-marker"></div>', unsafe_allow_html=True)
        btn_label = "☀️" if is_dark else "🌙"
        toggle_help = "Waiting for the agent" if toggle_disabled else "Toggle Light/Dark Theme"
        if st.button(btn_label, key="theme_toggle_btn", help=toggle_help, disabled=toggle_disabled):
            st.session_state["is_dark"] = not is_dark
            st.rerun()
