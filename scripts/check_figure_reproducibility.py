#!/usr/bin/env python3
"""Check that re-executed notebooks reproduce their committed figures.

`make verify-notebooks` writes executed copies to `.nbverify/`. This check
compares the figures in those copies with the committed notebooks, so a figure
that changes on every execution fails here instead of being rewritten into
history by the next re-render. PNGs are compared without their text chunks,
which hold metadata such as the matplotlib version. A cell whose figure cannot
reproduce, such as a wall-clock timing plot, carries the
`nondeterministic-output` tag and is skipped.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import struct
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXECUTED_DIR = REPO_ROOT / ".nbverify"
EXEMPT_TAG = "nondeterministic-output"
FIGURE_TYPES = ("image/png", "image/jpeg", "image/svg+xml")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
PNG_TEXT_CHUNKS = (b"tEXt", b"zTXt", b"iTXt")


def png_without_text(payload: str) -> str | bytes:
    """Return a base64 PNG's decoded bytes without its text chunks.

    Matplotlib writes its version into a ``tEXt`` chunk, so a dependency update
    would otherwise fail this check on figures whose pixels did not change.
    A payload that is not a well-formed PNG is returned unchanged.
    """
    try:
        data = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError):
        return payload
    if not data.startswith(PNG_SIGNATURE):
        return payload
    kept = [PNG_SIGNATURE]
    offset = len(PNG_SIGNATURE)
    while offset < len(data):
        if offset + 8 > len(data):
            return payload
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        chunk_type = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if end > len(data):
            return payload
        if chunk_type not in PNG_TEXT_CHUNKS:
            kept.append(data[offset:end])
        offset = end
    return b"".join(kept)


def cell_figures(cell: dict) -> list[tuple[str, str | bytes]]:
    """Return the ``(MIME type, comparable payload)`` of every figure a cell stores, in order."""
    figures = []
    for output in cell.get("outputs", []):
        data = output.get("data", {})
        for mime in FIGURE_TYPES:
            if mime in data:
                payload = data[mime]
                payload = "".join(payload) if isinstance(payload, list) else payload
                if mime == "image/png":
                    payload = png_without_text(payload)
                figures.append((mime, payload))
    return figures


def is_exempt(cell: dict) -> bool:
    return EXEMPT_TAG in cell.get("metadata", {}).get("tags", [])


def compare(name: str, committed: dict, executed: dict) -> list[str]:
    """Return one message per figure mismatch between two copies of a notebook."""
    committed_cells = committed["cells"]
    executed_cells = executed["cells"]
    sources_match = len(committed_cells) == len(executed_cells) and all(
        committed_cell["cell_type"] == executed_cell["cell_type"]
        and "".join(committed_cell["source"]) == "".join(executed_cell["source"])
        for committed_cell, executed_cell in zip(committed_cells, executed_cells)
    )
    if not sources_match:
        # Comparing figures across different sources would report the edit,
        # not a reproducibility defect.
        return [
            f"{name}: the executed copy was not produced from the committed "
            "sources. Re-run `make verify-notebooks` for this notebook."
        ]

    messages = []
    for index, (committed_cell, executed_cell) in enumerate(
        zip(committed_cells, executed_cells)
    ):
        if committed_cell["cell_type"] != "code":
            continue
        committed_figures = cell_figures(committed_cell)
        if is_exempt(committed_cell):
            if not committed_figures:
                messages.append(
                    f"{name}: cell {index} is tagged {EXEMPT_TAG!r} but stores no "
                    "figure. Remove the tag."
                )
            continue
        executed_figures = cell_figures(executed_cell)
        if len(committed_figures) != len(executed_figures):
            messages.append(
                f"{name}: cell {index} stores {len(committed_figures)} figure(s), "
                f"but re-execution produced {len(executed_figures)}."
            )
            continue
        changed = sum(
            committed_figure != executed_figure
            for committed_figure, executed_figure in zip(committed_figures, executed_figures)
        )
        if changed:
            messages.append(
                f"{name}: cell {index} has {changed} of {len(committed_figures)} "
                "figure(s) that re-execution did not reproduce."
            )
    return messages


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "notebooks",
        nargs="+",
        help="Committed notebook paths relative to the repository root.",
    )
    parser.add_argument(
        "--executed-dir",
        type=Path,
        default=EXECUTED_DIR,
        help="Directory holding the executed copies (default: .nbverify).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    messages = []
    for notebook in args.notebooks:
        committed_path = REPO_ROOT / notebook
        executed_path = args.executed_dir / committed_path.name
        if not executed_path.is_file():
            messages.append(
                f"{notebook}: no executed copy at {executed_path}. Run "
                "`make verify-notebooks` for this notebook first."
            )
            continue
        messages.extend(
            compare(
                notebook,
                json.loads(committed_path.read_text(encoding="utf-8")),
                json.loads(executed_path.read_text(encoding="utf-8")),
            )
        )

    if not messages:
        print(
            "Re-execution reproduced every committed figure in "
            f"{len(args.notebooks)} notebook(s)."
        )
        return 0

    print(f"{len(messages)} figure reproducibility problem(s):")
    for message in messages:
        print(f"  - {message}")
    print(
        "\nSeed the randomness behind the figure, or, when it can never reproduce "
        f"(for example a timing plot), tag the cell {EXEMPT_TAG!r}."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
