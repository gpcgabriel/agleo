"""Icons drawn onto the buttons a marker element precedes."""

from urllib.parse import quote

import streamlit as st

from app.ui.gui.icons import icon_cancel, icon_check, icon_moon, icon_play, icon_stop, icon_sun

# Matching the block Streamlit wraps around every element: a marker and the button
# after it each sit in one, side by side.
ELEMENT_CONTAINER = 'div[data-testid="stElementContainer"]'


def as_mask(svg: str) -> str:
    """Returns an inline SVG as a CSS mask, percent-encoded so its quotes cannot end the `url()`."""
    return f'url("data:image/svg+xml,{quote(svg)}") center / contain no-repeat'


def button_icon_rule(marker: str, svg: str) -> str:
    """Returns the rule that draws an icon before the label of the button following a marker.

    The icon is a mask over the label's own color, so it follows each theme and each
    button style; an SVG drawn as a background image would always come out black.

    Args:
        marker (str): CSS class of the marker drawn right before the button.
        svg (str): The icon, as inline SVG.

    Returns:
        str: One CSS rule.
    """
    mask = as_mask(svg)
    return (
        f"{ELEMENT_CONTAINER}:has(.{marker}) + {ELEMENT_CONTAINER} button::before {{ "
        'content: ""; display: inline-block; width: 16px; height: 16px; flex-shrink: 0; margin-right: 8px; '
        f"vertical-align: middle; background-color: currentColor; -webkit-mask: {mask}; mask: {mask}; }}"
    )


def theme_toggle_rule(svg: str) -> str:
    """Returns the rules that show the theme toggle as an icon instead of its text label.

    The label stays in the button, invisible, so screen readers still have a name for
    it; hiding it with color alone would not do, because an emoji keeps its own colors.
    The icon is painted over it in the theme's text color.

    Args:
        svg (str): The icon, as inline SVG.

    Returns:
        str: Three CSS rules.
    """
    mask = as_mask(svg)
    toggle = f"{ELEMENT_CONTAINER}:has(.theme-toggle-marker) + {ELEMENT_CONTAINER} button"
    return (
        f"{toggle} {{ position: relative; }} "
        f"{toggle} > div {{ opacity: 0; }} "
        f'{toggle}::after {{ content: ""; position: absolute; inset: 0; margin: auto; width: 18px; height: 18px; '
        f"background-color: var(--text-primary); -webkit-mask: {mask}; mask: {mask}; }}"
    )


def inject_css(is_dark: bool) -> None:
    """Injects the icons of the Initialize, Stop, Confirm, Cancel and theme toggle buttons.

    Each rule reaches its button through the marker drawn right before it, so this has to
    run after those buttons are on the page. The rules go out as a single line: Streamlit
    reads markdown before HTML, and a blank line would end the style block early.

    Args:
        is_dark (bool): Whether the dark theme is on, which the toggle answers with a sun.
    """
    rules = [
        button_icon_rule("btn-initialize-marker", icon_play(16)),
        button_icon_rule("btn-stop-marker", icon_stop(16)),
        button_icon_rule("btn-confirm-marker", icon_check(16)),
        button_icon_rule("btn-cancel-marker", icon_cancel(16)),
        theme_toggle_rule(icon_sun(18) if is_dark else icon_moon(18)),
    ]
    st.markdown(f"<style>{' '.join(rules)}</style>", unsafe_allow_html=True)
