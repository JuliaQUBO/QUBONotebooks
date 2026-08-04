from __future__ import annotations

import itertools
import json
import re
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "10-QAOA.ipynb"


def notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text())


def notebook_source() -> str:
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook()["cells"]
    )


def notebook_cell(data: dict, cell_id: str) -> dict:
    matches = [cell for cell in data["cells"] if cell.get("id") == cell_id]
    if len(matches) != 1:
        raise AssertionError(f"Expected one cell with id {cell_id!r}, found {len(matches)}")
    return matches[0]


def cell_output_text(cell: dict) -> str:
    output_parts = []
    for output in cell.get("outputs", []):
        value = output.get("text", output.get("data", {}).get("text/plain", ""))
        output_parts.append("".join(value) if isinstance(value, list) else value)
    return "\n".join(output_parts)


def binary_states(size: int) -> list[tuple[int, ...]]:
    return list(itertools.product((0, 1), repeat=size))


def qiskit_parameter_names(layers: int) -> list[str]:
    return [f"β[{layer}]" for layer in range(layers)] + [
        f"γ[{layer}]" for layer in range(layers)
    ]


def decode_qiskit_count_key(key: str) -> tuple[int, ...]:
    return tuple(int(bit) for bit in reversed(key.replace(" ", "")))


class QAOAMathematicalInvariantTests(unittest.TestCase):
    def test_number_partitioning_exact_baseline(self) -> None:
        weights = (1, 3, 4, 8)

        def raw_energy(bits: tuple[int, ...]) -> int:
            return sum(
                weight * (1 - 2 * bit) for weight, bit in zip(weights, bits)
            ) ** 2

        states = binary_states(len(weights))
        optimum = min(raw_energy(bits) for bits in states)
        optima = {bits for bits in states if raw_energy(bits) == optimum}

        self.assertEqual(0, optimum)
        self.assertEqual({(0, 0, 0, 1), (1, 1, 1, 0)}, optima)

    def test_maxcut_exact_baseline_and_sign(self) -> None:
        weighted_edges = (
            (1, 2, 2),
            (1, 3, 1),
            (2, 3, 2),
            (2, 4, 1),
            (3, 4, 3),
        )

        def cut_weight(bits: tuple[int, ...]) -> int:
            return sum(
                weight if bits[i - 1] != bits[j - 1] else 0
                for i, j, weight in weighted_edges
            )

        def raw_energy(bits: tuple[int, ...]) -> int:
            return -cut_weight(bits)

        states = binary_states(4)
        optimum = min(raw_energy(bits) for bits in states)
        optima = {bits for bits in states if raw_energy(bits) == optimum}

        self.assertEqual(-7, optimum)
        self.assertTrue(all(cut_weight(bits) == 7 for bits in optima))
        self.assertEqual(4, len(optima))

    def test_vertex_cover_exact_baseline_and_feasibility(self) -> None:
        edges = ((1, 2), (1, 3), (2, 3), (3, 4))
        penalty = 2

        def uncovered(bits: tuple[int, ...]) -> list[tuple[int, int]]:
            return [
                (i, j)
                for i, j in edges
                if bits[i - 1] == 0 and bits[j - 1] == 0
            ]

        def raw_energy(bits: tuple[int, ...]) -> int:
            return sum(bits) + penalty * len(uncovered(bits))

        states = binary_states(4)
        optimum = min(raw_energy(bits) for bits in states)
        optima = {bits for bits in states if raw_energy(bits) == optimum}

        self.assertEqual(2, optimum)
        self.assertEqual({(1, 0, 1, 0), (0, 1, 1, 0)}, optima)
        self.assertTrue(all(not uncovered(bits) for bits in optima))


class QAOANotebookOutputTests(unittest.TestCase):
    def test_notebook_commits_reproducible_local_outputs(self) -> None:
        data = notebook()
        code_cells = [cell for cell in data["cells"] if cell["cell_type"] == "code"]
        populated_cells = [cell for cell in code_cells if cell.get("outputs", [])]

        self.assertTrue(code_cells)
        self.assertEqual(
            list(range(1, len(code_cells) + 1)),
            [cell.get("execution_count") for cell in code_cells],
        )
        self.assertGreaterEqual(len(populated_cells), 12)
        self.assertEqual([], notebook_cell(data, "bootstrap").get("outputs", []))
        self.assertEqual([], notebook_cell(data, "activate").get("outputs", []))

        expected_output_markers = {
            "runtime-check": "Local runtime ready: QiskitOpt 0.7.1",
            "partition-run": "exact optimum raw energy = 0.0",
            "maxcut-run": "exact optimum raw energy = -7.0",
            "cover-run": "exact optimum raw energy = 2.0",
            "comparison": "Exact-versus-sampled energy summary",
            "fixed-circuits": "p=1 parameter order:",
            "resource-audits": "p=2 resources:",
            "bit-order": "QAOA.count_key_bits returns variable order",
            "ibm-handoff": "IBM handoff dry run:",
            "ibm-hardware": "IBM quantum hardware submission is disabled",
            "solution-bit-order": "Rendered key 1100 becomes variable-order bits",
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
        forbidden_markers = (
            "/home/",
            "/Users/",
            "C:\\Users",
            "AppData",
            "Bearer ",
            "QISKIT_IBM_TOKEN=",
            "QISKIT_IBM_INSTANCE=",
        )
        for marker in forbidden_markers:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, serialized_outputs)


if __name__ == "__main__":
    unittest.main()
