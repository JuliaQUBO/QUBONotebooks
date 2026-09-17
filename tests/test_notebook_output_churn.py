"""Contracts for the notebook output churn report in CONTRIBUTING.md."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from notebook_test_support import REPO_ROOT


MODULE_PATH = REPO_ROOT / "scripts" / "report_notebook_output_churn.py"
SPEC = importlib.util.spec_from_file_location("report_notebook_output_churn", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
churn = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = churn
SPEC.loader.exec_module(churn)

NOTEBOOK = "notebooks_py/a.ipynb"
OTHER = "notebooks_jl/b.ipynb"


def figure_notebook(*cells: tuple[str, list[str]]) -> dict:
    """Build a notebook of code cells, each ``(source, [png payloads])``."""
    return {
        "cells": [
            {
                "cell_type": "code",
                "metadata": {},
                "source": source,
                "outputs": [
                    {"output_type": "display_data", "metadata": {}, "data": {"image/png": png}}
                    for png in payloads
                ],
            }
            for source, payloads in cells
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 2,
    }


class OutputPayloadTests(unittest.TestCase):
    def test_counts_each_rich_value_and_stream_text_by_its_utf8_size(self) -> None:
        notebook = {
            "cells": [
                {
                    "cell_type": "code",
                    "outputs": [
                        {"data": {"image/png": ["ab", "cd"], "text/plain": "é"}},
                        {"output_type": "stream", "text": ["x\n"]},
                        {"data": {"application/json": {"k": 1}}},
                    ],
                },
                {"cell_type": "markdown", "source": "no outputs"},
            ]
        }

        self.assertEqual(
            [4, 2, 2, len(json.dumps({"k": 1}))],
            list(churn.output_payloads(notebook).values()),
        )

    def test_counts_a_repeated_payload_once(self) -> None:
        notebook = figure_notebook(("a", ["same"]), ("b", ["same"]))

        self.assertEqual([4], list(churn.output_payloads(notebook).values()))

    def test_an_absent_notebook_has_no_payloads(self) -> None:
        self.assertEqual({}, churn.output_payloads(None))


class RerenderedCellTests(unittest.TestCase):
    def test_counts_unchanged_sources_whose_output_changed(self) -> None:
        before = figure_notebook(("a", ["1"]), ("b", ["2"]), ("c", ["3"]))
        after = figure_notebook(("a", ["1"]), ("b", ["X"]), ("c-edited", ["Y"]))

        self.assertEqual(1, churn.rerendered_cells(before, after))

    def test_reports_zero_when_cells_were_added_or_the_notebook_is_new(self) -> None:
        before = figure_notebook(("a", ["1"]))
        after = figure_notebook(("a", ["X"]), ("b", ["2"]))

        self.assertEqual(0, churn.rerendered_cells(before, after))
        self.assertEqual(0, churn.rerendered_cells(None, after))


class HistoryTests(unittest.TestCase):
    """Walk a real throwaway repository, since the report's input is history."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        patcher = mock.patch.object(churn, "REPO_ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        env = {
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
        env_patcher = mock.patch.dict(os.environ, env)
        env_patcher.start()
        self.addCleanup(env_patcher.stop)
        self.git("init", "-q", "-b", "main")
        self.commit({NOTEBOOK: figure_notebook(("a", ["base-1"]), ("b", ["base-2"]))})

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def commit(self, files: dict[str, dict | str]) -> str:
        for name, content in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content if isinstance(content, str) else json.dumps(content))
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")
        return self.git("rev-parse", "HEAD")

    def measure(self) -> dict[str, tuple[int, int, int, int]]:
        _merge_base, entries = churn.measure("main", "HEAD")
        return {
            entry.path: (entry.commits, entry.new_payloads, entry.new_bytes, entry.rerendered)
            for entry in entries
        }

    def test_counts_payloads_new_to_the_notebook_across_every_branch_commit(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.commit({NOTEBOOK: figure_notebook(("a", ["base-1"]), ("b", ["new-12345"]))})
        self.commit({NOTEBOOK: figure_notebook(("a", ["base-1"]), ("b", ["newer-123"]))})
        # Reverting to an earlier payload adds nothing new.
        self.commit({NOTEBOOK: figure_notebook(("a", ["base-1"]), ("b", ["new-12345"]))})

        self.assertEqual({NOTEBOOK: (3, 2, 18, 1)}, self.measure())

    def test_payloads_already_in_the_base_version_are_free(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.commit({NOTEBOOK: figure_notebook(("a-edited", ["base-1"]), ("b", ["base-2"]))})

        self.assertEqual({NOTEBOOK: (1, 0, 0, 0)}, self.measure())

    def test_ignores_files_outside_the_notebook_directories_and_non_notebooks(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.commit(
            {
                "notebooks/old.ipynb": figure_notebook(("a", ["elsewhere"])),
                "notebooks_py/notes.md": "text",
                OTHER: figure_notebook(("a", ["julia"])),
            }
        )

        self.assertEqual({OTHER: (1, 1, 5, 0)}, self.measure())

    def test_measures_only_what_the_branch_adds_after_the_merge_base(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.commit({NOTEBOOK: figure_notebook(("a", ["base-1"]), ("b", ["branch"]))})
        self.git("switch", "-q", "main")
        self.commit({OTHER: figure_notebook(("a", ["main-only"]))})
        self.git("switch", "-q", "work")
        # Merging main in brings OTHER, but it is not the branch's churn.
        self.git("merge", "-q", "--no-edit", "main")

        self.assertEqual({NOTEBOOK: (1, 1, 6, 1)}, self.measure())

    def test_counts_a_notebook_the_merge_itself_rewrote(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.commit({NOTEBOOK: figure_notebook(("a", ["base-1"]), ("b", ["branch"]))})
        self.git("switch", "-q", "main")
        self.commit({NOTEBOOK: figure_notebook(("a", ["main-1"]), ("b", ["base-2"]))})
        self.git("switch", "-q", "work")
        self.git("merge", "-q", "--no-commit", "-s", "ours", "main")
        self.commit({NOTEBOOK: figure_notebook(("a", ["main-1"]), ("b", ["resolved"]))})

        # "main-1" is at the merge base and "base-1" at the original fork
        # point, so only "branch" and the merge's own "resolved" are new.
        self.assertEqual({NOTEBOOK: (2, 2, 14, 1)}, self.measure())

    def test_an_unparsable_version_adds_no_payload(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.commit({NOTEBOOK: "<<<<<<< conflict"})

        self.assertEqual({NOTEBOOK: (1, 0, 0, 0)}, self.measure())

    def test_main_prints_the_report_and_appends_the_step_summary(self) -> None:
        self.git("switch", "-q", "-c", "work")
        self.commit({NOTEBOOK: figure_notebook(("a", ["base-1"]), ("b", ["x" * 2048]))})
        summary = self.root / "summary.md"
        stdout = io.StringIO()
        with mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary)}):
            with redirect_stdout(stdout):
                status = churn.main(["--base", "main", "--head", "HEAD"])

        self.assertEqual(0, status)
        lines = stdout.getvalue().splitlines()
        self.assertEqual(f"| `{NOTEBOOK}` | 1 | 1 | 2.0 KB | 1 |", lines[4])
        self.assertEqual(
            "Total: 2.0 KB of output that neither the base nor an earlier commit on the "
            "branch stored.",
            lines[6],
        )
        self.assertEqual(
            f"## Notebook output churn\n\n{stdout.getvalue()}", summary.read_text()
        )

    def test_main_reports_a_branch_without_notebook_changes(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = churn.main(["--base", "main", "--head", "HEAD"])

        self.assertEqual(0, status)
        self.assertRegex(stdout.getvalue(), r"^No notebook changes between [0-9a-f]{12} and HEAD\.")

    def test_main_exits_nonzero_only_when_history_is_unreadable(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            status = churn.main(["--base", "no-such-ref"])

        self.assertEqual(2, status)
        self.assertRegex(stderr.getvalue(), r"^Could not read history: ")


class SizeFormatTests(unittest.TestCase):
    def test_formats_kilobytes_and_megabytes(self) -> None:
        self.assertEqual("0.5 KB", churn.format_size(512))
        self.assertEqual("1.50 MB", churn.format_size(1536 * 1024))


if __name__ == "__main__":
    unittest.main()
