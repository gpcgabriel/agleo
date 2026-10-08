"""Runs the whole test suite, or the groups and modules named on the command line, without pytest.

From the repository root, since tests open `datasets/` by relative path:

    python -m tests                                   # every test
    python -m tests engine agents/allocation          # the groups under those directories
    python -m tests tests/engine/test_topology.py     # one module

A test is any `test_*` function a `test_*.py` module under `tests/` defines; its
group is the directory the module sits in. Every test runs even after another
fails, and the run ends with one line per group and a non-zero exit status if any
test failed. `make check` runs the same functions through pytest instead.
"""

import argparse
import importlib
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent


class GroupResult:
    """The tests one group passed and failed, and how long they took."""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.seconds = 0.0


def parse_arguments() -> argparse.Namespace:
    """Returns: argparse.Namespace: The groups and modules to run, every test when none is named."""
    parser = argparse.ArgumentParser(
        prog="python -m tests", description="Runs the tests, or the ones named, without pytest."
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="groups (directories under tests/, like engine or agents/allocation) or test modules",
    )
    return parser.parse_args()


def resolve_target(target: str) -> Path:
    """Returns the group or module a target names, relative to `tests/` or to the repository root.

    Raises:
        SystemExit: If the target names nothing under `tests/`.
    """
    for base in (TESTS_DIR, ROOT):
        path = (base / target).resolve()
        if path.exists() and path.is_relative_to(TESTS_DIR):
            return path
    raise SystemExit(f"No test group or module at {target!r}; expected a directory or a test_*.py under {TESTS_DIR}.")


def find_modules(targets: list[str]) -> list[Path]:
    """Returns: list: The test modules under the targets, or under `tests/` when there are none, in path order."""
    modules = set()
    for root in [resolve_target(target) for target in targets] or [TESTS_DIR]:
        modules.update([root] if root.is_file() else root.rglob("test_*.py"))
    return sorted(modules)


def tests_of(module: ModuleType) -> list[tuple[str, Callable[[], object]]]:
    """Returns: list: The module's own `test_*` functions, in the order it defines them."""
    return [
        (name, value)
        for name, value in vars(module).items()
        if name.startswith("test_") and callable(value) and getattr(value, "__module__", None) == module.__name__
    ]


def run_test(name: str, test: Callable[[], object]) -> bool:
    """Runs one test and prints its outcome. Returns: bool: Whether it passed."""
    try:
        test()
    except AssertionError as error:
        print(f"  FAIL   {name}: {error}")
        return False
    except Exception:
        print(f"  ERROR  {name}\n{traceback.format_exc()}")
        return False
    print(f"  PASS   {name}")
    return True


def run_module(path: Path, result: GroupResult) -> None:
    """Runs every test of one module, adding its outcomes to its group's result."""
    print(f"\n{path.relative_to(ROOT)}")
    started = time.perf_counter()
    try:
        module = importlib.import_module(".".join(path.relative_to(ROOT).with_suffix("").parts))
    except Exception:
        print(f"  ERROR  importing the module\n{traceback.format_exc()}")
        result.failed += 1
        return
    for name, test in tests_of(module):
        if run_test(name, test):
            result.passed += 1
        else:
            result.failed += 1
    result.seconds += time.perf_counter() - started


def print_summary(results: dict[str, GroupResult]) -> None:
    """Prints one line per group and the totals."""
    width = max(len(group) for group in [*results, "total"])
    print(f"\n{'group':<{width}}  {'passed':>6}  {'failed':>6}  {'seconds':>7}")
    for group, result in results.items():
        print(f"{group:<{width}}  {result.passed:>6}  {result.failed:>6}  {result.seconds:>7.1f}")
    passed = sum(result.passed for result in results.values())
    failed = sum(result.failed for result in results.values())
    seconds = sum(result.seconds for result in results.values())
    print(f"{'total':<{width}}  {passed:>6}  {failed:>6}  {seconds:>7.1f}")


def main() -> int:
    """Runs the requested tests. Returns: int: The exit status, 1 when any test failed."""
    modules = find_modules(parse_arguments().targets)
    if not modules:
        raise SystemExit("No test modules found.")

    results = {}
    for path in modules:
        group = path.parent.relative_to(TESTS_DIR).as_posix()
        run_module(path, results.setdefault(group, GroupResult()))

    print_summary(results)
    return 1 if any(result.failed for result in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
