"""Tests for the light and dark stylesheets.

The light theme existed as a file for months while `apply_theme` loaded the
dark one unconditionally, so the toggle in the header moved a flag that reached
the map tiles and nothing else. These assert that both themes load, that they
differ, and that neither has drifted out of parity with the other.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ui.gui.styles import DARK_THEME_FILE, HTML_DIR, LIGHT_THEME_FILE, resolve_theme_file


def read_theme(is_dark):
    with open(resolve_theme_file(is_dark), encoding="utf-8") as stylesheet:
        return stylesheet.read()


def selectors_of(css):
    """Returns: set: Every selector the stylesheet declares."""
    without_comments = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return {
        selector.strip()
        for block in re.findall(r"([^{}]+)\{", without_comments)
        for selector in block.split(",")
        if selector.strip()
    }


def variables_of(css):
    """Returns: set: Every custom property the stylesheet defines."""
    return set(re.findall(r"(--[\w-]+)\s*:", css))


def test_each_theme_resolves_to_its_own_file():
    assert resolve_theme_file(True).endswith(DARK_THEME_FILE)
    assert resolve_theme_file(False).endswith(LIGHT_THEME_FILE)


def test_both_stylesheets_exist():
    for filename in (DARK_THEME_FILE, LIGHT_THEME_FILE):
        assert os.path.isfile(os.path.join(HTML_DIR, filename)), f"{filename} is missing"


def test_the_two_themes_are_not_the_same_file():
    assert read_theme(True) != read_theme(False)


def test_neither_theme_styles_something_the_other_ignores():
    """A selector on one side only means one theme is drifting out of parity."""
    dark, light = selectors_of(read_theme(True)), selectors_of(read_theme(False))

    assert dark - light == set(), f"only dark styles: {sorted(dark - light)}"
    assert light - dark == set(), f"only light styles: {sorted(light - dark)}"


def test_every_variable_one_theme_defines_the_other_defines_too():
    """A variable missing on one side renders as an invalid value, not a default."""
    dark, light = variables_of(read_theme(True)), variables_of(read_theme(False))

    assert dark - light == set(), f"only dark defines: {sorted(dark - light)}"
    assert light - dark == set(), f"only light defines: {sorted(light - dark)}"


def test_no_variable_is_referenced_without_being_defined():
    for is_dark in (True, False):
        css = read_theme(is_dark)
        defined = variables_of(css)
        used = set(re.findall(r"var\((--[\w-]+)", css))
        missing = used - defined

        assert missing == set(), f"{'dark' if is_dark else 'light'} uses undefined {sorted(missing)}"


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
