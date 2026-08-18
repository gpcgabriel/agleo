import streamlit as st

from app.gui.icons import icon_cancel, icon_check, icon_moon, icon_play, icon_stop, icon_sun


def inject_CSS(is_dark: bool) -> None:
    """Inject the CSS that overlays SVG icons onto the marker-tagged buttons
    (Initialize, Stop, Confirm, Cancel, Theme toggle). Must run after those
    buttons have been rendered, since it targets them via sibling selectors.
    """
    play_svg = icon_play(16).replace("#", "%23")
    stop_svg = icon_stop(16).replace("#", "%23")
    check_svg = icon_check(16).replace("#", "%23")
    cancel_svg = icon_cancel(16).replace("#", "%23")
    sun_svg = icon_sun(18).replace("#", "%23")
    moon_svg = icon_moon(18).replace("#", "%23")

    toggle_svg_uri = sun_svg if is_dark else moon_svg

    st.markdown(
        f"""
    <style>
    /* Inject Initialize button icon */
    div[data-testid="element-container"]:has(.btn-initialize-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{play_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}

    /* Inject Stop button icon */
    div[data-testid="element-container"]:has(.btn-stop-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{stop_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}

    /* Inject Confirm button icon */
    div[data-testid="element-container"]:has(.btn-confirm-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{check_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}

    /* Inject Cancel button icon */
    div[data-testid="element-container"]:has(.btn-cancel-marker) + div[data-testid="element-container"] button::before {{
        content: "";
        display: inline-block;
        width: 16px;
        height: 16px;
        margin-right: 8px;
        background-image: url("data:image/svg+xml;utf8,{cancel_svg}");
        background-size: contain;
        background-repeat: no-repeat;
        vertical-align: middle;
    }}

    /* Inject Theme Toggle button icon */
    div[data-testid="element-container"]:has(.theme-toggle-marker) + div[data-testid="element-container"] button {{
        background-image: url("data:image/svg+xml;utf8,{toggle_svg_uri}") !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        color: transparent !important;
    }}
    </style>
    """,
        unsafe_allow_html=True,
    )
