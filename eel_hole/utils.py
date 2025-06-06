"""Useful helper functions."""

import re

from frictionless import Package
from docutils.core import publish_parts

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


def clean_descriptions(datapackage: Package) -> Package:
    if datapackage.description:
        datapackage.description = rst_to_html(datapackage.description)
    for resource in datapackage.resources:
        resource.description = rst_to_html(resource.description)
        for field in resource.schema.fields:
            field.description = rst_to_html(field.description)
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
