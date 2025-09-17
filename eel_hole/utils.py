"""Useful helper functions."""

import html
import itertools
import re

from frictionless import Package
from docutils.core import publish_parts
from docutils.utils import SystemMessage

import structlog

log = structlog.get_logger(__name__)


SPHINX_TAGS = re.compile(r":(?:ref|func|doc):`([^`]+)`")


def rst_to_html(rst: str) -> str:
    """
    Convert a reStructuredText (reST) string to HTML.

    This function uses `docutils` to render valid reStructuredText into HTML5.
    Sphinx-style roles like `:ref:`, `:func:`, or `:doc:` are replaced with
    inline code formatting (``like this``) to ensure compatibility outside
    of Sphinx environments.

    The resulting HTML is extracted from the `html_body` part of the parsed document,
    which includes a `<main>` wrapper tag around the content.

    Args:
        rst (str): A string containing reStructuredText.

    Returns:
        str: The rendered HTML string, including a `<main>` wrapper.
    """
    cleaned_rst = re.sub(SPHINX_TAGS, r"``\1``", rst)
    # publish_parts lets us pick out just the body html and ignore the header info.
    # also we're dropping these descriptions under an h2 tag, so start all
    # included sections from h3.
    return publish_parts(
        cleaned_rst,
        writer_name="html5",
        settings_overrides={"initial_header_level": 3},
    )["html_body"]


def plaintext_to_html(text: str) -> str:
    """
    Convert plaintext with simple Markdown-style formatting to basic HTML.

    This function escapes HTML characters and supports limited formatting:
    - `**bold**` → <strong>bold</strong>
    - `*italic*` → <em>italic</em>
    - Unordered lists using `-` or `*` are wrapped in <ul>/<li> tags
    - Ordered lists using `1.`, `2.`, etc. are wrapped in <ol>/<li> tags
    - Double line breaks are interpreted as separating paragraphs
    - Single line breaks are preserved as literal '\n' inside paragraphs (no <br> tags)

    Args:
        text (str): Plaintext input string with optional Markdown-style formatting.

    Returns:
        str: HTML-formatted string.
    """
    escaped = html.escape(text)

    # Handle bold and italics (simple Markdown-style)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)

    paragraphs = re.split(r"\n\s*\n", escaped)
    html_parts = []

    for para in paragraphs:
        lines = para.splitlines()
        html_lines = []
        in_ul = False
        in_ol = False

        for line in lines:
            if re.match(r"^\s*[-*]\s+", line):
                # Switch from ol to ul if needed
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False
                if not in_ul:
                    html_lines.append("<ul>")
                    in_ul = True
                html_lines.append(f"<li>{line.strip()[2:]}</li>")

            elif re.match(r"^\s*\d+\.\s+", line):
                # Switch from ul to ol if needed
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                if not in_ol:
                    html_lines.append("<ol>")
                    in_ol = True
                html_lines.append(f"<li>{line.strip().split(None, 1)[1]}</li>")

            else:
                # Close any open lists before adding paragraph text line
                if in_ul:
                    html_lines.append("</ul>")
                    in_ul = False
                if in_ol:
                    html_lines.append("</ol>")
                    in_ol = False
                html_lines.append(line)  # keep \n inside paragraph as is

        # Close any lists still open at the end of the paragraph
        if in_ul:
            html_lines.append("</ul>")
        if in_ol:
            html_lines.append("</ol>")

        # Join paragraph lines with newline to preserve single line breaks
        joined_para = "\n".join(html_lines).strip()

        # Wrap non-list paragraphs in <p>
        if not (joined_para.startswith("<ul>") or joined_para.startswith("<ol>")):
            html_parts.append(f"<p>{joined_para}</p>")
        else:
            html_parts.append(joined_para)

    return f"<main>\n{'\n'.join(html_parts)}\n</main>"


def clean_pudl_descriptions(datapackage: Package) -> Package:
    """Clean up the PUDL datapackage descriptions for display.

    PUDL datapackage documentation is all in RST so we use Sphinx machinery to
    turn it into HTML that our Jinja templates understand.
    """
    if datapackage.description:
        datapackage.description = rst_to_html(datapackage.description)
    for resource in datapackage.resources:
        resource.description = rst_to_html(resource.description)
        for field in resource.schema.fields:
            field.description = rst_to_html(field.description)
    return datapackage


def clean_ferc_xbrl_descriptions(datapackage: Package) -> Package:
    """Clean up the FERC XBRL datapackage descriptions for display.

    These are written in no-format plaintext, so we have some custom HTML
    generation. Also, the table *descriptions* are useless but the table
    *titles* (not *name* which is the canonical name of the table) are merely
    nearly useless. So we replace the descriptions with the titles.

    Since some FERC table names appear in multiple forms, we need to prepend the
    form name to *all* the table names.
    """
    if datapackage.description:
        datapackage.description = plaintext_to_html(datapackage.description)
    for resource in datapackage.resources:
        resource.description = plaintext_to_html(resource.title)
        resource.name = f"{datapackage.sources[0]['title']}.{resource.name}"
        for field in resource.schema.fields:
            field.description = plaintext_to_html(field.description)
    return datapackage


def merge_datapackages(datapackages: list[Package]) -> Package:
    """Merge multiple frictionless `Package` objects into a single package.

    Resources from the input packages are combined into one, preserving the original order.
    If a resource with the same name appears more than once, only the first occurrence
    is included in the result; subsequent duplicates are skipped with a warning.

    Args:
        datapackages (list[Package]): A list of frictionless Package objects to merge.

    Returns:
        Package: A new frictionless Package containing the merged resources.
    """
    return Package.from_descriptor(
        {
            "resources": [
                res.to_descriptor() for pkg in datapackages for res in pkg.resources
            ]
        }
    )
