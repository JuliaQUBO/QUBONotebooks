from __future__ import annotations

import itertools
import json
import os
import re
import subprocess
import tomllib
import unittest
from pathlib import Path

from makefile_support import command_with_assignment


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "6-QCi.ipynb"
QCI_REVISION = "30a6074fdd5bd75c3f1cf965329edd01c67e63fe"


def notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text())


def notebook_source() -> str:
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook()["cells"]
    )


def notebook_cell(data: dict, cell_id: str) -> dict:
    matches = [cell for cell in data["cells"] if cell.get("id") == cell_id]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one cell with id {cell_id!r}, found {len(matches)}"
        )
    return matches[0]


def cell_output_text(cell: dict) -> str:
    parts = []
    for output in cell.get("outputs", []):
        value = output.get("text", output.get("data", {}).get("text/plain", ""))
        parts.append("".join(value) if isinstance(value, list) else value)
    return "\n".join(parts)


def small_qubo_energy(bits: tuple[int, ...]) -> int:
    return (sum(bits) - 1) ** 2


class QCIJuliaNotebookTests(unittest.TestCase):


    def test_local_target_masks_cloud_state_and_selects_qci_notebook(self) -> None:
        env = os.environ.copy()
        env.pop("MAKEFLAGS", None)
        env.pop("MFLAGS", None)
        # Hostile ambient values must not turn the local check into a QCI job.
        env.update(
            {
                "QCI_TOKEN": "test-only",
                "QUBONOTEBOOKS_QCI_ENABLE_CLOUD": "1",
                "QUBONOTEBOOKS_QCI_REQUIRE_CLOUD": "1",
            }
        )
        completed = subprocess.run(
            ["make", "--dry-run", "verify-qci-julia-local"],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        command = command_with_assignment(completed.stdout, "NOTEBOOKS")
        assignments = dict(
            token.split("=", 1) for token in command if "=" in token
        )

        self.assertEqual(
            [
                "env",
                "-u",
                "JULIA_CONDAPKG_BACKEND",
                "-u",
                "JULIA_PYTHONCALL_EXE",
                "-u",
                "QCI_TOKEN",
            ],
            command[:7],
        )
        self.assertEqual("0", assignments["QUBONOTEBOOKS_QCI_ENABLE_CLOUD"])
        self.assertEqual("0", assignments["QUBONOTEBOOKS_QCI_REQUIRE_CLOUD"])
        self.assertEqual("--group docs", assignments["UV_GROUP_FLAGS"])
        self.assertEqual("notebooks_jl/6-QCi.ipynb", assignments["NOTEBOOKS"])

    def test_cloud_target_fails_closed_without_opt_in(self) -> None:
        env = os.environ.copy()
        env.pop("MAKEFLAGS", None)
        env.pop("MFLAGS", None)
        for variable in (
            "QCI_TOKEN",
            "QUBONOTEBOOKS_QCI_ENABLE_CLOUD",
            "QUBONOTEBOOKS_QCI_REQUIRE_CLOUD",
        ):
            env.pop(variable, None)
        completed = subprocess.run(
            ["make", "verify-qci-julia-cloud"],
            cwd=REPO_ROOT,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(2, completed.returncode)
        self.assertIn(
            "QUBONOTEBOOKS_QCI_ENABLE_CLOUD",
            completed.stdout + completed.stderr,
        )

    def test_committed_outputs_publish_sanitized_qci_results(self) -> None:
        data = notebook()
        code_cells = [
            cell for cell in data["cells"] if cell.get("cell_type") == "code"
        ]
        live_cell = notebook_cell(data, "qci-live")
        output_text = "\n".join(cell_output_text(cell) for cell in code_cells)

        self.assertTrue(code_cells)
        self.assertTrue(
            all(cell.get("execution_count") is not None for cell in code_cells)
        )
        live_output = cell_output_text(live_cell)
        self.assertIn("Validated", live_output)
        self.assertRegex(live_output, re.compile(r"result 1: bits=\[[01, ]+\]"))
        self.assertIn("energy=", live_output)
        self.assertIn("multiplicity=", live_output)
        self.assertNotIn("QCI cloud submission skipped", live_output)
        self.assertNotRegex(output_text, re.compile(r"(?i)bearer\s+[a-z0-9._-]+"))
        self.assertNotRegex(output_text, re.compile(r"(?i)\bjob[_ -]?id\b"))
        self.assertNotRegex(output_text, re.compile(r"(?i)\baccount\b"))


if __name__ == "__main__":
    unittest.main()
