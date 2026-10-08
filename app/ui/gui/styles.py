import json
import os

import streamlit as st

from app.core.slash_commands import get_commands_for_js

# Pointing at the directory that holds the HTML and CSS assets.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(BASE_DIR, "html")


DARK_THEME_FILE = "theme_dark.css"
LIGHT_THEME_FILE = "theme_light.css"
# Naming the rules both themes share, which follow the chosen theme's palette.
BASE_THEME_FILE = "theme_base.css"


def resolve_theme_file(is_dark: bool) -> str:
    """Returns the stylesheet that matches the requested theme.

    Args:
        is_dark (bool): Whether the dark theme is on.

    Returns:
        str: Absolute path of the stylesheet to inject.
    """
    return os.path.join(HTML_DIR, DARK_THEME_FILE if is_dark else LIGHT_THEME_FILE)


def apply_theme(is_dark: bool) -> None:
    """Injects the stylesheet for the requested theme: its palette, then the rules both themes share.

    Args:
        is_dark (bool): Whether the dark theme is on.

    Raises:
        FileNotFoundError: If a stylesheet is missing. A theme that silently
            fails to load leaves the operator on Streamlit's defaults, which
            look close enough to working to go unnoticed.
    """
    # Injecting the stylesheet with no leading whitespace before the style tag.
    st.markdown(f"<style>\n{build_theme_css(is_dark)}\n</style>", unsafe_allow_html=True)


def build_theme_css(is_dark: bool) -> str:
    """Returns: str: The requested theme's palette followed by the rules both themes share."""
    stylesheets = []
    for filepath in (resolve_theme_file(is_dark), os.path.join(HTML_DIR, BASE_THEME_FILE)):
        with open(filepath, encoding="utf-8") as stylesheet:
            stylesheets.append(stylesheet.read())
    return "\n".join(stylesheets)


def inject_accessibility_script() -> None:
    """Injects the accessibility attributes, landmarks and the slash menu.

    The script is loaded inside an iframe so that its HTML and JS do not leak
    into the visible DOM. Nothing theme-dependent is interpolated into it: the
    menu it builds reads the palette through CSS variables, which keeps the
    injected text identical between renders, and an iframe whose content does
    not change is one Streamlit does not remount.
    """
    js_filepath = os.path.join(HTML_DIR, "accessibility.js")
    try:
        with open(js_filepath, encoding="utf-8") as f:
            js_content = f.read()

        commands_json = json.dumps(get_commands_for_js(), ensure_ascii=False)

        # Appending the execution call so the script runs on iframe load.
        js_content_with_call = (
            js_content + f"\nif (typeof initAccessibility === 'function') {{ initAccessibility({commands_json}); }}"
        )

        # Reading the script from a file in this project: it never comes from
        # operator input or from model output.
        #
        # `st.iframe` rejects height=0, so the iframe is given 1px and the
        # marker below lets the stylesheet collapse the surrounding block.
        st.markdown('<div class="a11y-script-marker"></div>', unsafe_allow_html=True)
        st.iframe(f"<script>\n{js_content_with_call}\n</script>", height=1)
    except Exception as e:
        st.error(f"Error loading accessibility JS: {e}")
