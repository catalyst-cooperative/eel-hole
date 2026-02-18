#!/usr/bin/env python3
"""Build static marimo example exports from configured notebook sources."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class ExampleConfig:
    slug: str
    title: str
    source_path: str
    description: str | None


@dataclass(frozen=True)
class SourceConfig:
    repo_url: str | None
    repo_ref: str | None


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        cmd_str = " ".join(cmd)
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {cmd_str}"
        )


def load_config(config_path: Path) -> tuple[SourceConfig, list[ExampleConfig]]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("examples config must be a mapping")

    source_raw = raw.get("source", {})
    if source_raw is None:
        source_raw = {}
    if not isinstance(source_raw, dict):
        raise ValueError("source must be a mapping")

    source = SourceConfig(
        repo_url=source_raw.get("repo_url"),
        repo_ref=source_raw.get("repo_ref"),
    )

    examples_raw = raw.get("examples")
    if examples_raw is None:
        raise ValueError("examples config must define an examples list")
    if not isinstance(examples_raw, list):
        raise ValueError("examples must be a list")

    examples: list[ExampleConfig] = []
    seen_slugs: set[str] = set()
    for index, item in enumerate(examples_raw):
        if not isinstance(item, dict):
            raise ValueError(f"examples[{index}] must be a mapping")

        slug = item.get("slug")
        title = item.get("title")
        source_path = item.get("source_path")

        if not isinstance(slug, str) or not SLUG_PATTERN.match(slug):
            raise ValueError(
                f"examples[{index}].slug must match {SLUG_PATTERN.pattern}: {slug!r}"
            )
        if slug in seen_slugs:
            raise ValueError(f"duplicate slug in config: {slug}")
        seen_slugs.add(slug)

        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"examples[{index}].title must be a non-empty string")
        if not isinstance(source_path, str) or not source_path.strip():
            raise ValueError(
                f"examples[{index}].source_path must be a non-empty string"
            )

        description = item.get("description")
        if description is not None and not isinstance(description, str):
            raise ValueError(f"examples[{index}].description must be a string")

        examples.append(
            ExampleConfig(
                slug=slug,
                title=title.strip(),
                source_path=source_path,
                description=description.strip()
                if isinstance(description, str)
                else None,
            )
        )

    return source, examples


def resolve_repo(
    *,
    repo_path: Path | None,
    source: SourceConfig,
    repo_url_override: str | None,
    repo_ref_override: str | None,
) -> tuple[Path, dict[str, Any], tempfile.TemporaryDirectory[str] | None]:
    if repo_path:
        resolved = repo_path.resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(
                f"--repo-path does not exist or is not a directory: {repo_path}"
            )
        return (
            resolved,
            {
                "repo_path": str(resolved),
            },
            None,
        )

    repo_url = repo_url_override or source.repo_url
    repo_ref = repo_ref_override or source.repo_ref

    if not repo_url or not repo_ref:
        raise ValueError(
            "repo URL/ref are required when --repo-path is not provided. "
            "Set source.repo_url + source.repo_ref in config or pass --repo-url/--repo-ref."
        )

    temp_dir = tempfile.TemporaryDirectory(prefix="examples-repo-")
    repo_root = Path(temp_dir.name)
    _run(["git", "clone", repo_url, str(repo_root)])
    _run(["git", "checkout", repo_ref], cwd=repo_root)

    return (
        repo_root,
        {
            "repo_url": repo_url,
            "repo_ref": repo_ref,
        },
        temp_dir,
    )


def build_examples(
    *,
    examples: list[ExampleConfig],
    repo_root: Path,
    output_dir: Path,
) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for example in examples:
        notebook_path = repo_root / example.source_path
        if not notebook_path.exists() or not notebook_path.is_file():
            raise FileNotFoundError(
                f"Notebook for slug '{example.slug}' not found: {notebook_path}"
            )

        slug_output_dir = output_dir / example.slug
        slug_output_dir.mkdir(parents=True, exist_ok=True)
        output_html = slug_output_dir / "index.html"

        _run(
            [
                "uv",
                "run",
                "marimo",
                "export",
                "html-wasm",
                str(notebook_path),
                "--mode",
                "run",
                "--force",
                "-o",
                str(output_html),
            ]
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export configured marimo notebooks as static HTML examples."
    )
    parser.add_argument(
        "--config",
        default="eel_hole/examples.yaml",
        type=Path,
        help="Path to examples YAML config.",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("eel_hole/static/examples"),
        type=Path,
        help="Directory where exported examples are written.",
    )
    parser.add_argument(
        "--repo-path",
        type=Path,
        default=None,
        help="Use an existing local source repo checkout instead of cloning.",
    )
    parser.add_argument(
        "--repo-url",
        type=str,
        default=None,
        help="Override source repo URL configured in the examples config file.",
    )
    parser.add_argument(
        "--repo-ref",
        type=str,
        default=None,
        help="Override source repo ref configured in the examples config file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source, examples = load_config(args.config)

    if not examples:
        if args.output_dir.exists():
            shutil.rmtree(args.output_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        return 0

    repo_root, _, temp_dir = resolve_repo(
        repo_path=args.repo_path,
        source=source,
        repo_url_override=args.repo_url,
        repo_ref_override=args.repo_ref,
    )

    try:
        build_examples(
            examples=examples,
            repo_root=repo_root,
            output_dir=args.output_dir,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
