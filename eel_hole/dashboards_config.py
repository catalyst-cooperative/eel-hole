"""Shared loading/validation for dashboard gallery configuration."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class DashboardConfig(BaseModel):
    """Configuration for a single hosted dashboard in the gallery.

    slug: short name for the dashboard URL in this app.
    title: title to display in gallery card.
    description: description to display in gallery card.
    thumbnail_path: app-relative image URL for the card thumbnail under
        /static/img/. Use a 4:3 image, ideally around 1200x900 pixels,
        so cards render consistently.
    thumbnail_alt_text: meaningful alt text for the dashboard screenshot.
    url: absolute URL to the hosted dashboard HTML.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    thumbnail_path: str = Field(min_length=1, pattern=r"^/static/img/.+")
    thumbnail_alt_text: str = Field(min_length=1)
    url: str = Field(min_length=1)


def load_dashboards_config(path: Path) -> list[DashboardConfig]:
    """Shim from YAML into Pydantic."""
    if not path.exists():
        raise ValueError(f"Dashboards config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raw = []

    return TypeAdapter(list[DashboardConfig]).validate_python(raw)
