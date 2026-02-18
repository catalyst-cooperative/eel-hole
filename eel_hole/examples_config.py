"""Shared loading/validation for examples gallery configuration."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ExampleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    title: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    description: str | None = None


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_url: str | None = None
    repo_ref: str | None = None


class ExamplesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SourceConfig = Field(default_factory=SourceConfig)
    examples: list[ExampleConfig] = Field(default_factory=list)


def load_examples_config(path: Path) -> ExamplesConfig:
    if not path.exists():
        return ExamplesConfig()

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raw = {}

    try:
        return ExamplesConfig.model_validate(raw)
    except ValidationError as exc:
        raise ValueError(f"Invalid examples config at {path}: {exc}") from exc
