"""Enforces the boundary between application logic and the interface.

The project's structural rule: `streamlit` may only be imported inside
`app/ui`. Every module under `app/core` or `app/agents` must work without the
interface — that is what allows headless simulation runs, agent tests without
mocks, and later on exposing the simulation through something other than the
dashboard.
"""

import ast
import importlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(ROOT))

DOMAIN_PACKAGES = ("app/core", "app/agents")
UI_PACKAGE = "app/ui"


def imported_modules(path):
    """Returns: set: Names of the modules the file imports."""
    names = set()

    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)

    return names


def test_domain_packages_never_import_streamlit():
    offenders = []

    for package in DOMAIN_PACKAGES:
        for path in (ROOT / package).rglob("*.py"):
            if any(name.split(".")[0] == "streamlit" for name in imported_modules(path)):
                offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"streamlit imported outside app/ui: {offenders}"


def test_domain_packages_never_import_the_ui_package():
    offenders = []

    for package in DOMAIN_PACKAGES:
        for path in (ROOT / package).rglob("*.py"):
            if any(name.startswith("app.ui") for name in imported_modules(path)):
                offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"app/ui imported by the domain layer: {offenders}"


def test_domain_packages_import_without_streamlit_loaded():
    """Runtime check: importing the domain must not load Streamlit, not even
    indirectly."""
    script = (
        "import sys;"
        "sys.path.insert(0, %r);"
        "import app.core.session, app.core.executor, app.core.router,"
        " app.core.catalog, app.core.handlers, app.agents.runner;"
        "assert 'streamlit' not in sys.modules, 'streamlit was loaded';"
        "print('ok')" % str(ROOT)
    )
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)

    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout


def test_every_ui_module_lives_under_the_ui_package():
    """No interface module may sit loose outside `app/ui`."""
    stray = []

    for path in (ROOT / "app").rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith(UI_PACKAGE):
            continue
        if any(name.split(".")[0] == "streamlit" for name in imported_modules(path)):
            stray.append(relative)

    assert not stray, f"interface modules outside app/ui: {stray}"


def test_the_domain_modules_are_importable():
    for name in ("app.core.session", "app.core.router", "app.core.handlers", "app.agents.runner"):
        assert importlib.import_module(name) is not None


if __name__ == "__main__":
    from runner import run_module_tests

    sys.exit(1 if run_module_tests(globals()) else 0)
