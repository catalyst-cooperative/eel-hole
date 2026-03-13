"""Pytest hooks for relevancy reporting."""

from tests.relevancy.reporting import render_variant_report
from pathlib import Path


def pytest_configure(config):
    """Initialize an in-memory collector for relevancy report blocks."""
    config._relevancy_reports = {}
    config._sweep_results = []


def pytest_addoption(parser):
    parser.addoption(
        "--experiment", action="store", default=None, help="experiment config YAML"
    )


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print consolidated relevancy metrics at the end of the test session."""
    reports = getattr(config, "_relevancy_reports", {})
    sweep_results = getattr(config, "_sweep_results", [])
    if not reports and not sweep_results:
        return

    if reports:
        include_worst_queries = config.getoption("verbose") >= 1

        terminalreporter.section("relevancy diagnostics", sep="=")
        for variant in sorted(reports):
            report = reports[variant]
            terminalreporter.write_line(
                render_variant_report(
                    variant=variant,
                    report=report,
                    include_worst_queries=include_worst_queries,
                )
            )
    if sweep_results:
        experiment = Path(config.getoption("experiment"))

        with open(f"sweep.{experiment.stem}.out", "w") as f:
            f.write("\n".join(sweep_results))
