"""Shared loading/validation for examples gallery configuration."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class ExampleConfig(BaseModel):
    """Configuration for a single example in the gallery.

    slug: short name for the example URL in this app.
    title: title to display in gallery card.
    description: description to display in gallery card.
    url: absolute URL to the hosted HTML example.
    """

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    url: str = Field(min_length=1)


def load_examples_config(path: Path) -> list[ExampleConfig]:
    """Shim from YAML into Pydantic."""
    if not path.exists():
        raise ValueError(f"Examples config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raw = []

    return TypeAdapter(list[ExampleConfig]).validate_python(raw)
