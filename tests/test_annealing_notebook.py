from __future__ import annotations

import itertools
import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "11-Annealing.ipynb"

PARTITION_WEIGHTS = (1, 3, 4, 8)
MAXCUT_EDGES = (
    (1, 2, 2),
    (1, 3, 1),
    (2, 3, 2),
    (2, 4, 1),
    (3, 4, 3),
)
COVER_EDGES = ((1, 2), (1, 3), (2, 3), (3, 4))
COVER_PENALTY = 2
ORDER_VALUES = (2, 3, 4, 5, 6, 8)
ORDER_EXPOSURES = (
    (1, 1, 2, 5, 4, 5),
    (4, -2, 3, 6, -3, 0),
)


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


def active_source(cell_source: str) -> str:
    """Cell source with Julia comment text removed.

    A guard assertion must not be satisfiable by a marker that survives only
    inside a comment, which is exactly what a disabled check looks like.
    """
    return "\n".join(
        line.split("#", 1)[0].rstrip() for line in cell_source.splitlines()
    )


def index_of(source: str, marker: str) -> int:
    position = source.find(marker)
    if position == -1:
        raise AssertionError(f"Expected executable {marker!r} in the guarded cell")
    return position


def binary_states(size: int) -> list[tuple[int, ...]]:
    return list(itertools.product((0, 1), repeat=size))


def partition_energy(bits: tuple[int, ...]) -> int:
    return sum(
        weight * (1 - 2 * bit)
        for weight, bit in zip(PARTITION_WEIGHTS, bits)
    ) ** 2


def maxcut_weight(bits: tuple[int, ...]) -> int:
    return sum(
        weight if bits[i - 1] != bits[j - 1] else 0
        for i, j, weight in MAXCUT_EDGES
    )


def cover_energy(bits: tuple[int, ...]) -> int:
    uncovered = sum(
        bits[i - 1] == 0 and bits[j - 1] == 0 for i, j in COVER_EDGES
    )
    return sum(bits) + COVER_PENALTY * uncovered


def order_energy(bits: tuple[int, ...]) -> int:
    value_imbalance = sum(
        value * (1 - 2 * bit) for value, bit in zip(ORDER_VALUES, bits)
    )
    risk_imbalances = (
        sum(exposure * (2 * bit - 1) for exposure, bit in zip(row, bits))
        for row in ORDER_EXPOSURES
    )
    return 2 * value_imbalance**2 + sum(value**2 for value in risk_imbalances)


class AnnealingMathematicalInvariantTests(unittest.TestCase):
    def test_partition_exact_baseline(self) -> None:
        states = binary_states(4)
        best = min(partition_energy(bits) for bits in states)
        optima = {bits for bits in states if partition_energy(bits) == best}

        self.assertEqual(0, best)
        self.assertEqual({(0, 0, 0, 1), (1, 1, 1, 0)}, optima)

    def test_maxcut_exact_baseline(self) -> None:
        states = binary_states(4)
        best_weight = max(maxcut_weight(bits) for bits in states)
        optima = {bits for bits in states if maxcut_weight(bits) == best_weight}

        self.assertEqual(7, best_weight)
        self.assertEqual(4, len(optima))

    def test_vertex_cover_exact_baseline_is_feasible(self) -> None:
        states = binary_states(4)
        best = min(cover_energy(bits) for bits in states)
        optima = {bits for bits in states if cover_energy(bits) == best}

        self.assertEqual(2, best)
        self.assertEqual({(1, 0, 1, 0), (0, 1, 1, 0)}, optima)
        self.assertTrue(
            all(
                all(bits[i - 1] or bits[j - 1] for i, j in COVER_EDGES)
                for bits in optima
            )
        )

    def test_order_partitioning_exact_baseline(self) -> None:
        states = binary_states(6)
        best = min(order_energy(bits) for bits in states)
        optima = {bits for bits in states if order_energy(bits) == best}

        self.assertEqual(28, best)
        self.assertEqual(2, len(optima))
        optimum_imbalances = {
            abs(
                sum(
                    value * (1 - 2 * bit)
                    for value, bit in zip(ORDER_VALUES, bits)
                )
            )
            for bits in optima
        }
        self.assertEqual({2}, optimum_imbalances)


class AnnealingNotebookOutputTests(unittest.TestCase):
    def test_notebook_commits_reproducible_local_outputs(self) -> None:
        data = notebook()
        code_cells = [cell for cell in data["cells"] if cell["cell_type"] == "code"]

        self.assertTrue(code_cells)
        self.assertEqual(
            list(range(1, len(code_cells) + 1)),
            [cell.get("execution_count") for cell in code_cells],
        )
        self.assertEqual([], notebook_cell(data, "bootstrap").get("outputs", []))
        self.assertEqual([], notebook_cell(data, "activate").get("outputs", []))
        self.assertEqual([], notebook_cell(data, "imports").get("outputs", []))

        expected_output_markers = {
            "runtime-check": "Local annealing runtime ready",
            "problem-catalog": "Prepared five solver-interchangeable models",
            "local-comparison": "Seeded DWave.Neal comparison",
            "comparison-table": "cancer-genomics aggregate",
            "qpu-run": "D-Wave QPU execution is disabled",
            "solution-temperature": "uphill acceptance",
            "solution-timing": "QPU access time",
        }
        for cell_id, marker in expected_output_markers.items():
            with self.subTest(cell_id=cell_id):
                self.assertIn(marker, cell_output_text(notebook_cell(data, cell_id)))

        self.assertFalse(
            any(
                output.get("output_type") == "error"
                for cell in code_cells
                for output in cell.get("outputs", [])
            )
        )
        serialized_outputs = json.dumps(
            [cell.get("outputs", []) for cell in code_cells], ensure_ascii=False
        )
        for marker in (
            "/home/",
            "/Users/",
            "C:\\Users",
            "AppData",
            "~/repos/",
            ".julia-depot/packages",
            "Bearer ",
            "DWAVE_API_TOKEN=",
        ):
            with self.subTest(forbidden_output_marker=marker):
                self.assertNotIn(marker, serialized_outputs)


class AnnealingRemoteHardwareGuardTests(unittest.TestCase):
    def test_qpu_submission_stays_behind_the_opt_in_and_credential_gate(self) -> None:
        # Defect class: the opt-in branch or the credential check is deleted or
        # commented out of the QPU cell without re-executing, so the committed
        # "disabled" output still matches while a Colab reader submits a billable
        # D-Wave job. No make target or CI job runs this notebook, so only this
        # test notices.
        source = active_source("".join(notebook_cell(notebook(), "qpu-run")["source"]))

        opt_in_gate = index_of(source, "if qpu_requested\n")
        credentials = index_of(source, "require_qpu_credentials()")
        submission = index_of(source, "run_annealing(maxcut_problem, qpu_config)")
        disabled_branch = index_of(source[opt_in_gate:], "\nelse\n") + opt_in_gate

        self.assertLess(opt_in_gate, credentials)
        self.assertLess(credentials, submission)
        self.assertLess(submission, disabled_branch)


if __name__ == "__main__":
    unittest.main()
