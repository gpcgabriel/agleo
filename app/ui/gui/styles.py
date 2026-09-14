import streamlit as st
import os
import json

from app.core.slash_commands import get_commands_for_js

# Base directory for HTML/CSS assets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(BASE_DIR, "html")


def apply_theme(is_dark: bool):
    """
    Applies custom Material design aesthetics for both light and dark themes using custom CSS.
    """
    theme_file = "theme_dark.css"  # if is_dark else "theme_light.css"
    filepath = os.path.join(HTML_DIR, theme_file)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            css_content = f.read()

        # Inject stylesheet without any leading whitespaces/newlines before the style tag
        st.markdown(f"<style>\n{css_content}\n</style>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading theme: {e}")


def inject_accessibility_script(is_dark: bool = False, *args, **kwargs):
    """
    Injects custom accessibility attributes and landmarks,
    along with a floating slash commands menu (similar to Antigravity 2.0 chat).
    The script is loaded inside an iframe so that its HTML/JS does not leak
    into the visible DOM.
    """
    js_filepath = os.path.join(HTML_DIR, "accessibility.js")
    try:
        with open(js_filepath, "r", encoding="utf-8") as f:
            js_content = f.read()

        is_dark_js = "true" if is_dark else "false"
        commands_json = json.dumps(get_commands_for_js(), ensure_ascii=False)

        # Append execution call so it runs immediately on iframe load
        js_content_with_call = (
            js_content
            + f"\nif (typeof initAccessibility === 'function') {{ initAccessibility({is_dark_js}, {commands_json}); }}"
        )

        # The script is always ours, read from a file in this project: it
        # never comes from operator input or model output.
        #
        # `st.iframe` rejects height=0, so the iframe is given 1px and the
        # marker below lets the stylesheet collapse the surrounding block.
        st.markdown('<div class="a11y-script-marker"></div>', unsafe_allow_html=True)
        st.iframe(f"<script>\n{js_content_with_call}\n</script>", height=1)
    except Exception as e:
        st.error(f"Error loading accessibility JS: {e}")
