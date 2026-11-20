"""Options shared by every test category.

The tests live in subdirectories by category: ``unit`` (no running app), ``integration``
(Playwright against the running app) and ``relevancy`` (search quality against the
running app). Command-line options must be registered here, in the root conftest:
pytest only reads ``pytest_addoption`` from conftest files at or above the paths it is
given, so an option registered in a subdirectory fails with "unrecognized arguments"
when running ``pytest tests``. Fixtures and hooks that belong to one category stay in
that category's own ``conftest.py``.
"""


def pytest_addoption(parser):
    parser.addoption(
        "--experiment",
        action="store",
        default=None,
        help="Search relevancy experiment config YAML (tests/relevancy)",
    )
