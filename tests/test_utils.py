import pytest
import json
from frictionless import Package, Resource, Schema, Field

from eel_hole.utils import (
    clean_descriptions,
    rst_to_html,
    plaintext_to_html,
    to_html,
    merge_datapackages,
)


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


def test_plaintext_to_html_basic_formatting():
    text = "This is *italic* and **bold** text.\nNext line."
    html_output = plaintext_to_html(text)
    assert "<em>italic</em>" in html_output
    assert "<strong>bold</strong>" in html_output
    assert "Next line.<br>" in html_output


def test_plaintext_to_html_lists():
    text = "- item one\n- item two\n1. first\n2. second"
    html_output = plaintext_to_html(text)
    assert "<ul>" in html_output
    assert "<ol>" in html_output
    assert "<li>item one</li>" in html_output
    assert "<li>second</li>" in html_output


def test_to_html_rst_valid():
    text = "Some text with a :ref:`link`."
    html_output = to_html(text)
    assert "<main>" in html_output
    assert "link" in html_output


def test_clean_descriptions():
    pkg = Package(
        {
            "name": "test",
            "description": "A *simple* description.",
            "resources": [
                {
                    "name": "res1",
                    "description": "1. First\n2. Second",
                    "data": [],  # <-- Required field added
                    "schema": {
                        "fields": [
                            {
                                "name": "field1",
                                "type": "string",
                                "description": "**bold** field",
                            }
                        ]
                    },
                }
            ],
        }
    )
    cleaned = clean_descriptions(pkg)

    assert "<em>simple</em>" in cleaned.description
    res_desc = cleaned.get_resource("res1").description
    assert "<ol" in res_desc and "<li><p>First</p></li>" in res_desc
    field_desc = cleaned.get_resource("res1").schema.get_field("field1").description
    assert "<strong>bold</strong>" in field_desc
