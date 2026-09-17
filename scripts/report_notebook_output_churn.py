#!/usr/bin/env python3
"""Report the notebook output a branch adds to repository history.

The size budgets bound what the notebooks store now. This report covers the
other quantity: every commit that rewrites a notebook's output adds the new
payloads to history for good, because base64 figures barely delta-compress.

For each notebook the branch touches, it walks every commit on the branch and
counts the output payloads that neither the merge-base version of that notebook
nor an earlier commit on the branch stored. It also counts the code cells whose
output differs from the merge base although their source does not, which is
what an unintended re-render looks like.

The report is informational. It exits 0 whenever it can read the history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DIRS = ("notebooks_jl", "notebooks_py")
KILOBYTE = 1024


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout


def read_notebook(commit: str, path: str) -> dict | None:
    """Return the notebook at ``commit``, or None when it is absent or unparsable."""
    try:
        return json.loads(git("show", f"{commit}:{path}"))
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


def output_payloads(notebook: dict | None) -> dict[str, int]:
    """Return every stored output value, keyed by content hash, with its size in bytes.

    Each MIME entry of a rich output counts separately, so a figure is counted
    once even when its text fallback is unchanged.
    """
    payloads: dict[str, int] = {}
    if notebook is None:
        return payloads
    for cell in notebook.get("cells", []):
        for output in cell.get("outputs", []):
            values = list(output.get("data", {}).values())
            if "text" in output:
                values.append(output["text"])
            for value in values:
                if isinstance(value, list):
                    value = "".join(value)
                elif not isinstance(value, str):
                    value = json.dumps(value, sort_keys=True)
                encoded = value.encode("utf-8")
                payloads[hashlib.sha256(encoded).hexdigest()] = len(encoded)
    return payloads


def rerendered_cells(before: dict | None, after: dict | None) -> int:
    """Count code cells whose source is unchanged but whose output differs.

    Cells are matched by position, so the count is only meaningful while the
    cell layout is unchanged; a notebook whose cells were added or removed
    reports 0 rather than a misleading figure.
    """
    if before is None or after is None:
        return 0
    before_cells, after_cells = before.get("cells", []), after.get("cells", [])
    if len(before_cells) != len(after_cells):
        return 0
    return sum(
        old.get("cell_type") == new.get("cell_type") == "code"
        and "".join(old.get("source", [])) == "".join(new.get("source", []))
        and old.get("outputs", []) != new.get("outputs", [])
        for old, new in zip(before_cells, after_cells)
    )


@dataclass
class NotebookChurn:
    path: str
    commits: int = 0
    new_payloads: int = 0
    new_bytes: int = 0
    rerendered: int = 0
    seen: set[str] = field(default_factory=set, repr=False)

    def record(self, payloads: dict[str, int]) -> None:
        self.commits += 1
        for digest, size in payloads.items():
            if digest not in self.seen:
                self.seen.add(digest)
                self.new_payloads += 1
                self.new_bytes += size


def changed_notebooks(commit: str) -> list[str]:
    """Return the notebooks ``commit`` changed relative to every one of its parents.

    For a merge, a notebook that matches one parent was carried over from that
    side unchanged, so only a notebook the merge itself rewrote counts.
    """
    parents = git("rev-list", "--parents", "-n", "1", commit).split()[1:]
    changed = None
    for parent in parents:
        names = git(
            "diff-tree", "-r", "--name-only", "--no-commit-id", parent, commit,
            "--", *NOTEBOOK_DIRS,
        )
        paths = {name for name in names.splitlines() if name.endswith(".ipynb")}
        changed = paths if changed is None else changed & paths
    return sorted(changed or ())


def measure(base: str, head: str) -> tuple[str, list[NotebookChurn]]:
    """Walk ``merge-base(base, head)..head`` and return the per-notebook churn."""
    merge_base = git("merge-base", base, head).strip()
    commits = git("rev-list", "--reverse", "--topo-order", f"{merge_base}..{head}").split()
    churn: dict[str, NotebookChurn] = {}
    for commit in commits:
        for path in changed_notebooks(commit):
            if path not in churn:
                base_payloads = output_payloads(read_notebook(merge_base, path))
                churn[path] = NotebookChurn(path, seen=set(base_payloads))
            churn[path].record(output_payloads(read_notebook(commit, path)))
    for path, entry in churn.items():
        entry.rerendered = rerendered_cells(
            read_notebook(merge_base, path), read_notebook(head, path)
        )
    return merge_base, sorted(churn.values(), key=lambda entry: (-entry.new_bytes, entry.path))


def format_size(size_bytes: int) -> str:
    if size_bytes >= KILOBYTE * KILOBYTE:
        return f"{size_bytes / (KILOBYTE * KILOBYTE):.2f} MB"
    return f"{size_bytes / KILOBYTE:.1f} KB"


def report(merge_base: str, head: str, churn: list[NotebookChurn]) -> str:
    if not churn:
        return f"No notebook changes between {merge_base[:12]} and {head}."
    rows = [
        f"| `{entry.path}` | {entry.commits} | {entry.new_payloads} | "
        f"{format_size(entry.new_bytes)} | {entry.rerendered} |"
        for entry in churn
    ]
    total = sum(entry.new_bytes for entry in churn)
    return "\n".join(
        [
            f"Notebook output added to history since {merge_base[:12]}:",
            "",
            "| Notebook | Commits | New outputs | New output bytes | Re-rendered unchanged cells |",
            "| --- | ---: | ---: | ---: | ---: |",
            *rows,
            "",
            f"Total: {format_size(total)} of output that neither the base nor an earlier "
            "commit on the branch stored.",
            "Re-rendered unchanged cells are code cells whose source is unchanged but "
            "whose output differs from the base.",
            "This report is informational and does not gate the pull request.",
        ]
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main", help="Branch the work merges into.")
    parser.add_argument("--head", default="HEAD", help="Tip of the work to measure.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        merge_base, churn = measure(args.base, args.head)
    except subprocess.CalledProcessError as exc:
        print(f"Could not read history: {exc.stderr.strip() or exc}", file=sys.stderr)
        return 2
    text = report(merge_base, args.head, churn)
    print(text)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(f"## Notebook output churn\n\n{text}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
