import pytest
from frictionless import Package, Resource, Schema, Field

from eel_hole.utils import (
    clean_ferc_xbrl_resource,
    clean_pudl_resource,
    rst_to_html,
    plaintext_to_html,
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


def test_plaintext_to_html_basic_formatting():
    text = "This is *italic* and **bold** text.\n\nNext paragraph.\nIgnore single linebreak."
    html_output = plaintext_to_html(text)

    # Check formatting
    assert "<em>italic</em>" in html_output, (
        "Expected italic text to be wrapped in <em> tags."
    )
    assert "<strong>bold</strong>" in html_output, (
        "Expected bold text to be wrapped in <strong> tags."
    )

    # Check paragraph wrapping
    assert (
        "<p>This is <em>italic</em> and <strong>bold</strong> text.</p>" in html_output
    ), "Expected first paragraph to be wrapped in <p> tags with correct formatting."
    assert "<p>Next paragraph.\nIgnore single linebreak.</p>" in html_output, (
        "Expected second paragraph to be wrapped in <p> tags with single newline preserved."
    )


def test_plaintext_to_html_lists():
    text = "- item one\n- item two\n1. first\n2. second"
    html_output = plaintext_to_html(text)
    assert "<ul>" in html_output
    assert "<ol>" in html_output
    assert "<li>item one</li>" in html_output
    assert "<li>second</li>" in html_output


def test_clean_pudl_resource():
    resource = Resource(
        name="res1",
        description="1. First\n2. Second",
        data=[],  # <-- Required field added
        schema=Schema(
            fields=[
                Field(
                    name="field1",
                    description="**bold** field",
                )
            ]
        ),
    )
    cleaned = clean_pudl_resource(resource, source_key="pudl_parquet")

    resource_description = str(cleaned.description)
    assert (
        "<ol" in resource_description
        and "<li><p>First</p></li>" in resource_description
    )
    field_description = str(cleaned.schema.get_field("field1").description)
    assert "<strong>bold</strong>" in field_description


def test_clean_ferc_xbrl_resource():
    resource = Resource(
        name="res1",
        title="Something useful",
        data=[],  # <-- Required field added
        schema=Schema(
            fields=[
                Field(
                    name="field1",
                    description="RST would require two newlines here:\n1. First\n2. Second",
                )
            ]
        ),
    )
    cleaned = clean_ferc_xbrl_resource(resource, source_key="ferc1_xbrl")

    resource_description = str(cleaned.description)
    assert "Something useful" in resource_description
    field_description = str(cleaned.schema.get_field("field1").description)
    assert "<ol" in field_description and "<li>First</li>" in field_description
