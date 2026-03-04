"""Pytest hooks for relevancy reporting."""

from tests.relevancy.reporting import render_variant_report


def pytest_configure(config):
    """Initialize an in-memory collector for relevancy report blocks."""
    config._relevancy_reports = {}


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print consolidated relevancy metrics at the end of the test session."""
    reports = getattr(config, "_relevancy_reports", {})
    if not reports:
        return
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
