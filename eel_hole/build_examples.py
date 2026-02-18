#!/usr/bin/env python3
"""Build static marimo example exports from configured notebook sources."""

import argparse
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from eel_hole.examples_config import ExampleConfig, SourceConfig, load_examples_config


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        cmd_str = " ".join(cmd)
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {cmd_str}"
        )


@contextmanager
def resolved_repo_dir(
    *,
    local_repo_path: Path | None,
    source: SourceConfig,
    remote_repo_url: str | None,
    remote_repo_ref: str | None,
) -> Iterator[Path]:
    if local_repo_path:
        resolved = local_repo_path.resolve()
        if not resolved.exists() or not resolved.is_dir():
            raise ValueError(
                f"--local-repo-path does not exist or is not a directory: {local_repo_path}"
            )
        yield resolved
        return

    repo_url = remote_repo_url or source.repo_url
    repo_ref = remote_repo_ref or source.repo_ref

    if not repo_url or not repo_ref:
        raise ValueError(
            "Need either --local-repo-path, or a remote source via "
            "--remote-repo-url + --remote-repo-ref (or source.repo_url + "
            "source.repo_ref in config)."
        )

    with tempfile.TemporaryDirectory(prefix="examples-repo-") as temp_dir:
        repo_root = Path(temp_dir)
        _run(["git", "clone", repo_url, str(repo_root)])
        _run(["git", "checkout", repo_ref], cwd=repo_root)
        yield repo_root


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
        "--local-repo-path",
        "--repo-path",
        dest="local_repo_path",
        type=Path,
        default=None,
        help="Use an existing local source repo checkout instead of cloning.",
    )
    parser.add_argument(
        "--remote-repo-url",
        "--repo-url",
        dest="remote_repo_url",
        type=str,
        default=None,
        help="Override source repo URL configured in the examples config file.",
    )
    parser.add_argument(
        "--remote-repo-ref",
        "--repo-ref",
        dest="remote_repo_ref",
        type=str,
        default=None,
        help="Override source repo ref configured in the examples config file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_examples_config(args.config)

    if not config.examples:
        if args.output_dir.exists():
            shutil.rmtree(args.output_dir)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        return

    with resolved_repo_dir(
        local_repo_path=args.local_repo_path,
        source=config.source,
        remote_repo_url=args.remote_repo_url,
        remote_repo_ref=args.remote_repo_ref,
    ) as repo_root:
        build_examples(
            examples=config.examples,
            repo_root=repo_root,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()
