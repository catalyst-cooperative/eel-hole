"""Shared loading/validation for parameter sweep configuration."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class SweepConfig(BaseModel):
    """Configuration for a parameter sweep for a single search variant."""

    model_config = ConfigDict(extra="forbid")

    class BeatConfig(BaseModel):
        model_config = ConfigDict(extra="forbid")
        map: float
        params: list[float]

    variant: str = Field(min_length=1)
    beat: BeatConfig
    center: list[float]
    sweep: dict[str, list[float]]


def load_sweep_config(path: Path) -> SweepConfig:
    """Shim from YAML into Pydantic."""
    if not path.exists():
        raise ValueError(f"Sweep config not found: {path}")

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if raw is None:
        raw = []

    return SweepConfig.model_validate(raw)
