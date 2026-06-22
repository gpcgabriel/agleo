import streamlit as st
import os
import json

from gui.slash_commands import get_commands_for_js

# Base directory for HTML/CSS assets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(BASE_DIR, "html")

def apply_theme(is_dark: bool):
    """
    Applies custom Material design aesthetics for both light and dark themes using custom CSS.
    """
    theme_file = "theme_dark.css" if is_dark else "theme_light.css"
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
    Uses a separate javascript file loaded via an iframe components helper
    to prevent visual DOM HTML/JS leaks.
    """
    import streamlit.components.v1 as components

    # Load and inject accessibility.js via components.html
    js_filepath = os.path.join(HTML_DIR, "accessibility.js")
    try:
        with open(js_filepath, "r", encoding="utf-8") as f:
            js_content = f.read()

        is_dark_js = "true" if is_dark else "false"
        commands_json = json.dumps(get_commands_for_js(), ensure_ascii=False)

        # Append execution call so it runs immediately on iframe load
        js_content_with_call = js_content + f"\nif (typeof initAccessibility === 'function') {{ initAccessibility({is_dark_js}, {commands_json}); }}"

        # Inject hidden component iframe to load the script
        components.html(f"<script>\n{js_content_with_call}\n</script>", height=0)
    except Exception as e:
        st.error(f"Error loading accessibility JS: {e}")
