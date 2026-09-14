"""Minimal test runner shared by the test modules.

The project has no pytest dependency: each test module is executable on its
own and reports through this helper.
"""


def run_module_tests(namespace):
    """Runs every `test_*` callable found in a module namespace.

    Args:
        namespace (dict): The calling module's `globals()`.

    Returns:
        int: How many tests failed.
    """
    names = sorted(name for name in namespace if name.startswith("test_"))
    failures = 0

    for name in names:
        try:
            namespace[name]()
            print(f"  PASS  {name}")
        except AssertionError as error:
            failures += 1
            print(f"  FAIL  {name}: {error}")

    print(f"\n{'OK' if not failures else f'{failures} failure(s)'}")
    return failures
