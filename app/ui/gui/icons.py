def icon_satellite(size: int = 20) -> str:
    """Returns an inline SVG string for a satellite icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="8" y="7" width="4" height="6" rx="1" />'
        '<path d="M3 9h5M12 9h5" />'
        '<rect x="1" y="7" width="2" height="6" rx="0.5" />'
        '<rect x="17" y="7" width="2" height="6" rx="0.5" />'
        '<path d="M10 3v4M10 13v4" />'
        "</svg>"
    )


def icon_globe(size: int = 20) -> str:
    """Returns an inline SVG string for a globe icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="10" cy="10" r="8" />'
        '<path d="M10 2a10 10 0 0 0 0 16 10 10 0 0 0 0-16M2 10h16" />'
        "</svg>"
    )


def icon_bot(size: int = 20) -> str:
    """Returns an inline SVG string for a bot icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<rect width="14" height="9" x="3" y="8" rx="2" />'
        '<circle cx="10" cy="3" r="1.5" />'
        '<path d="M10 4.5v3.5M7 12.5h.01M13 12.5h.01M5 8V6.5a1.5 1.5 0 0 1 1.5-1.5h7A1.5 1.5 0 0 1 15 6.5V8" />'
        "</svg>"
    )


def icon_play(size: int = 20) -> str:
    """Returns an inline SVG string for a play icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polygon points="6 4 16 10 6 16" fill="currentColor" />'
        "</svg>"
    )


def icon_stop(size: int = 20) -> str:
    """Returns an inline SVG string for a stop icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="4" y="4" width="12" height="12" rx="2" fill="currentColor" />'
        "</svg>"
    )


def icon_check(size: int = 20) -> str:
    """Returns an inline SVG string for a check icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="16 5 8 13 4 9" />'
        "</svg>"
    )


def icon_cancel(size: int = 20) -> str:
    """Returns an inline SVG string for a cancel/close icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="15" y1="5" x2="5" y2="15" />'
        '<line x1="5" y1="5" x2="15" y2="15" />'
        "</svg>"
    )


def icon_users(size: int = 20) -> str:
    """Returns an inline SVG string for a users icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M13 17v-1.5a2.5 2.5 0 0 0-2.5-2.5h-5A2.5 2.5 0 0 0 3 15.5V17" />'
        '<circle cx="8" cy="7.5" r="3" />'
        '<path d="M17 17v-1a2.5 2.5 0 0 0-2-2.45" />'
        '<path d="M13.5 4.1a3 3 0 0 1 0 5.8" />'
        "</svg>"
    )


def icon_station(size: int = 20) -> str:
    """Returns an inline SVG string for a ground station icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 10l8-8 8 8" />'
        '<path d="M10 4v12" />'
        '<path d="M8 16h4" />'
        "</svg>"
    )


def icon_chart(size: int = 20) -> str:
    """Returns an inline SVG string for a chart icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="15" y1="17" x2="15" y2="8" />'
        '<line x1="10" y1="17" x2="10" y2="3" />'
        '<line x1="5" y1="17" x2="5" y2="12" />'
        "</svg>"
    )


def icon_sun(size: int = 20) -> str:
    """Returns an inline SVG string for a sun icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="10" cy="10" r="3" />'
        '<path d="M10 2v2M10 16v2M4.34 4.34l1.42 1.42M14.24 14.24l1.42 1.42M2 10h2M16 10h2M5.76 14.24l-1.42 1.42M15.66 4.34l-1.42 1.42" />'
        "</svg>"
    )


def icon_moon(size: int = 20) -> str:
    """Returns an inline SVG string for a moon icon (20x20 default)."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 20 20" '
        'fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M10 3a5 5 0 0 0 7.5 7.5 7.5 7.5 0 1 1-7.5-7.5Z" />'
        "</svg>"
    )


def wrap_icon(svg_str: str, margin_right: int = 6) -> str:
    """Helper to wrap SVG string in a styled span block for inline alignment."""
    return f'<span style="display: inline-flex; align-self: center; align-items: center; justify-content: center; vertical-align: middle; margin-right: {margin_right}px; line-height: 1;">{svg_str}</span>'
