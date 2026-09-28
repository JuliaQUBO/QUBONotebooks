#!/usr/bin/env python3
"""Build student and instructor workshop bundles from the tracked collection."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT_FILES = {
    ".python-version", "LICENSE", "Makefile", "README.md", "CONTRIBUTING.md",
    "index.md", "local-setup.md", "workshops.md", "myst.yml", "colab.html",
    "pyproject.toml", "uv.lock",
}
RUNTIME_DIRS = {"notebooks_py", "notebooks_jl", "notebooks_data", "scripts"}
SOLUTION_MARKER = re.compile(r"^\s*#\s*SOLUTION\b", re.MULTILINE)
EXERCISE_MARKER = re.compile(r"^\s*#\s*EXERCISE\b", re.MULTILINE)
COLAB_BADGE = re.compile(
    r'<a\b[^>]*href=["\']https://colab\.research\.google\.com/[^>]*>.*?</a>',
    re.DOTALL | re.IGNORECASE,
)


def workshop_notebook(notebook: dict, edition: str) -> tuple[dict, int]:
    """Return an independent edition and the number of solution cells found.

    Student copies remove solution cells and clear exercise outputs. Instructor
    copies reveal solution cells. Worked examples and their outputs are kept.
    """
    if edition not in {"student", "instructor"}:
        raise ValueError(f"Unknown workshop edition: {edition}")
    result = copy.deepcopy(notebook)
    cells = []
    solutions = 0
    for cell in result["cells"]:
        source = "".join(cell["source"])
        metadata = cell.setdefault("metadata", {})
        tags = metadata.get("tags", [])
        solution = "solution" in tags or bool(SOLUTION_MARKER.search(source))
        if solution:
            solutions += 1
            if edition == "student":
                continue
            metadata["tags"] = [tag for tag in tags if tag not in {"hide-cell", "hide-input", "hide-output"}]
            metadata.pop("collapsed", None)
            for key in ("source_hidden", "outputs_hidden"):
                metadata.get("jupyter", {}).pop(key, None)
        if edition == "student" and cell["cell_type"] == "code" and (
            "exercise" in tags or EXERCISE_MARKER.search(source)
        ):
            cell["outputs"] = []
            cell["execution_count"] = None
            metadata.pop("execution", None)
            metadata.pop("ExecuteTime", None)
        if cell["cell_type"] == "markdown":
            source = COLAB_BADGE.sub(
                f"<p>{edition.capitalize()} workshop edition. To use Colab, upload this notebook file.</p>",
                source,
            )
            source = source.replace(
                "Click the badge above to open this notebook in Colab.",
                "Upload this workshop notebook to Colab.",
            ).replace("Open the badge above", "Upload this workshop notebook to Colab")
            cell["source"] = source.splitlines(keepends=True)
        cells.append(cell)
    result["cells"] = cells
    result.setdefault("metadata", {})["qubonotebooks_workshop"] = {"edition": edition}
    if edition == "student":
        # Widget state can retain rendered answers after a cell is removed.
        result["metadata"].pop("widgets", None)
    return result, solutions


def archive_bundle(directory: Path, destination: Path) -> None:
    """Write a ZIP whose bytes do not depend on filesystem timestamps."""
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                name = (Path(directory.name) / path.relative_to(directory)).as_posix()
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())


def build_workshops(root: Path, destination: Path, editions: tuple[str, ...]) -> list[Path]:
    """Export tracked lesson/runtime files to a new directory, leaving sources intact.

    Refusing an existing destination protects notes or exercise answers added
    to a previously generated workshop. Each edition has its own ZIP and a
    manifest recording source revision, local modifications, and output hashes.
    """
    root = root.resolve()
    destination = destination.resolve()

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True)

    if Path(git("rev-parse", "--show-toplevel").strip()).resolve() != root:
        raise ValueError("Build workshops from the original repository checkout.")
    if destination.exists():
        raise FileExistsError(f"Choose a new output directory; {destination} already exists.")
    tracked = [Path(name) for name in git("ls-files", "-z").split("\0") if name]
    paths = sorted(path for path in tracked if path.as_posix() in ROOT_FILES or path.parts[0] in RUNTIME_DIRS)
    notebooks = [path for path in paths if path.suffix == ".ipynb"]
    if not notebooks:
        raise ValueError("No tracked notebooks found.")
    revision = git("rev-parse", "HEAD").strip()
    dirty = bool(git("status", "--porcelain", "--untracked-files=no").strip())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".workshop-export-", dir=destination.parent) as staging:
        staging_path = Path(staging)
        payload = staging_path / "workshops"
        payload.mkdir()
        for edition in editions:
            directory = payload / edition
            hashes = {}
            solution_counts = {}
            for relative in paths:
                source = root / relative
                if source.is_symlink() or not source.is_file():
                    raise ValueError(f"Expected a regular tracked file: {relative}")
                data = source.read_bytes()
                if relative.as_posix() == "README.md" and Path("workshops.md") in paths:
                    intro = (
                        f"**{edition.capitalize()} workshop edition.** "
                        "Start with the [workshop guide](workshops.md).\n\n"
                    )
                    data = intro.encode() + data
                if relative.suffix == ".ipynb":
                    notebook, count = workshop_notebook(json.loads(data), edition)
                    data = (json.dumps(notebook, indent=1, ensure_ascii=False) + "\n").encode()
                    solution_counts[relative.as_posix()] = count
                target = directory / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                hashes[relative.as_posix()] = hashlib.sha256(data).hexdigest()
            manifest = {
                "schema_version": 1,
                "edition": edition,
                "source_commit": revision,
                "source_has_local_changes": dirty,
                "solution_cells": solution_counts,
                "files_sha256": hashes,
            }
            (directory / "workshop-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
            archive_bundle(directory, payload / f"{edition}.zip")
        payload.rename(destination)
    return [destination / f"{edition}.zip" for edition in editions]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("dist/workshops"), help="New destination directory (must not already exist).")
    parser.add_argument("--edition", choices=("student", "instructor", "both"), default="both")
    args = parser.parse_args()
    editions = ("student", "instructor") if args.edition == "both" else (args.edition,)
    for path in build_workshops(Path(__file__).resolve().parents[1], args.output_dir, editions):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
