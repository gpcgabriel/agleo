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
# Naming the scripts run in the page: the accessibility fixes and slash menu, and the fade between themes.
PAGE_SCRIPT_FILES = ("accessibility.js", "theme_transition.js")


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


def inject_page_scripts() -> None:
    """Injects the accessibility attributes, landmarks and slash menu, and the fade between themes.

    The scripts are loaded inside an iframe so that their HTML and JS do not leak
    into the visible DOM. Nothing theme-dependent is interpolated into them: the
    menu they build reads the palette through CSS variables, which keeps the
    injected text identical between renders, and an iframe whose content does
    not change is one Streamlit does not remount.
    """
    try:
        sources = []
        for filename in PAGE_SCRIPT_FILES:
            with open(os.path.join(HTML_DIR, filename), encoding="utf-8") as script:
                sources.append(script.read())

        commands_json = json.dumps(get_commands_for_js(), ensure_ascii=False)

        # Appending the calls that start the scripts once the iframe has loaded them.
        sources.append(f"if (typeof initAccessibility === 'function') {{ initAccessibility({commands_json}); }}")
        sources.append("if (typeof initThemeTransition === 'function') { initThemeTransition(); }")

        # Reading the scripts from files in this project: they never come from
        # operator input or from model output.
        #
        # `st.iframe` rejects height=0, so the iframe is given 1px and the
        # marker below lets the stylesheet collapse the surrounding block.
        st.markdown('<div class="a11y-script-marker"></div>', unsafe_allow_html=True)
        st.iframe("<script>\n" + "\n".join(sources) + "\n</script>", height=1)
    except Exception as e:
        st.error(f"Error loading the page scripts: {e}")
