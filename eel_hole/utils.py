"""Useful helper functions."""

import html
import re

from frictionless import Package
from docutils.core import publish_parts
from docutils.utils import SystemMessage

import structlog

log = structlog.get_logger(__name__)


SPHINX_TAGS = re.compile(r":(?:ref|func|doc):`([^`]+)`")


def rst_to_html(rst: str) -> str:
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
    escaped = html.escape(text)

    # Handle bold and italics (simple Markdown-style)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)

    # Detect lists (bulleted or numbered)
    lines = escaped.splitlines()
    html_lines = []
    in_ul = in_ol = False

    for line in lines:
        if re.match(r"^\s*[-*]\s+", line):
            if not in_ul:
                html_lines.append("<ul>")
                in_ul = True
            html_lines.append(f"<li>{line.strip()[2:]}</li>")
        elif re.match(r"^\s*\d+\.\s+", line):
            if not in_ol:
                html_lines.append("<ol>")
                in_ol = True
            html_lines.append(f"<li>{line.strip().split(None, 1)[1]}</li>")
        else:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            html_lines.append(line + "<br>")

    if in_ul:
        html_lines.append("</ul>")
    if in_ol:
        html_lines.append("</ol>")

    return "\n".join(html_lines)


def to_html(text: str) -> str:
    try:
        return rst_to_html(text)
    except SystemMessage:
        # If invalid RST, fallback to plaintext HTML conversion
        return plaintext_to_html(text)


def clean_descriptions(datapackage: Package) -> Package:
    if datapackage.description:
        datapackage.description = to_html(datapackage.description)
    for resource in datapackage.resources:
        resource.description = to_html(resource.description)
        for field in resource.schema.fields:
            field.description = to_html(field.description)
    return datapackage


def merge_datapackages(datapackages: list[Package]) -> Package:
    seen_names = set()
    all_resources = []

    for pkg in datapackages:
        for res in pkg.resources:
            if res.name not in seen_names:
                all_resources.append(res.to_descriptor())
                seen_names.add(res.name)
            else:
                log.warning(f"Duplicate resource name skipped: {res.name}")

    return Package.from_descriptor({"resources": all_resources})
