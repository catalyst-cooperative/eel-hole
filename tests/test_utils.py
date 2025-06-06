import pytest
import json
from frictionless import Package

from eel_hole.utils import rst_to_html, merge_datapackages


@pytest.fixture
def make_package():
    def _make_package(resource_names):
        return Package.from_descriptor(
            {"resources": [{"name": name, "data": []} for name in resource_names]}
        )

    return _make_package


def test_rst_to_html():
    really_bad_string = (
        ":ref:`reference` :doc:`document` :func:`function` normal text ``some code``"
    )
    expected_output = (
        "<main><p>"
        '<span class="docutils literal">reference</span>'
        " "
        '<span class="docutils literal">document</span>'
        " "
        '<span class="docutils literal">function</span>'
        " normal text "
        '<span class="docutils literal">some code</span>'
        "</p></main>"
    )
    assert rst_to_html(really_bad_string).replace("\n", "") == expected_output


def test_merge_distinct_packages(make_package):
    pkg1 = make_package(["table_a"])
    pkg2 = make_package(["table_b"])
    merged = merge_datapackages([pkg1, pkg2])
    resource_names = [res.name for res in merged.resources]
    assert set(resource_names) == {"table_a", "table_b"}


def test_merge_with_duplicates(make_package, capsys):
    pkg1 = make_package(["table_a", "table_b"])
    pkg2 = make_package(["table_b", "table_c"])

    merged = merge_datapackages([pkg1, pkg2])
    resource_names = [res.name for res in merged.resources]
    assert set(resource_names) == {"table_a", "table_b", "table_c"}
    assert len(resource_names) == 3

    # Capture stdout where structlog prints JSON logs
    captured = capsys.readouterr()

    # structlog outputs one JSON log per line, so parse lines separately
    log_events = []
    for line in captured.out.strip().split("\n"):
        try:
            log_json = json.loads(line)
            log_events.append(log_json.get("event", ""))
        except json.JSONDecodeError:
            # Skip lines that aren't valid JSON
            pass

    assert "Duplicate resource name skipped: table_b" in log_events


def test_merge_empty_input():
    merged = merge_datapackages([])
    assert isinstance(merged, Package)
    assert merged.resources == []
