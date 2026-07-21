from __future__ import annotations

import itertools
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "7-CanonicalProblems.ipynb"


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


def assert_source_contains(
    test_case: unittest.TestCase, source: str, marker: str
) -> None:
    test_case.assertTrue(marker in source, f"Missing notebook source marker: {marker!r}")


def assert_source_excludes(
    test_case: unittest.TestCase, source: str, marker: str
) -> None:
    test_case.assertFalse(marker in source, f"Forbidden notebook source marker: {marker!r}")


class CanonicalProblemsNotebookSourceTests(unittest.TestCase):
    def test_notebook_has_tutorial_structure_and_clean_room_references(self) -> None:
        source = notebook_source()
        required_sections = (
            "## Setup",
            "## Learning objectives",
            "## Prerequisites",
            "## Number partitioning",
            "## Max-Cut",
            "## Minimum vertex cover",
            "## Practice checkpoints",
            "## Summary",
            "## References",
        )

        for section in required_sections:
            with self.subTest(section=section):
                assert_source_contains(self, source, section)

        assert_source_contains(self, source, "https://doi.org/10.1287/educ.2025.0288")
        assert_source_contains(
            self,
            source,
            "https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers",
        )
        assert_source_contains(self, source.lower(), "original julia derivations")

    def test_notebook_uses_public_deterministic_credential_free_path(self) -> None:
        source = notebook_source()

        required_markers = (
            "QUBO.ExactSampler.Optimizer",
            "evaluate_jump_objective",
            "assert_all_states_match",
            "exact_sampler_optima!",
            "fixed_positions",
            "partition_weights = [1, 3, 4, 8]",
            "(3, 4, 3),",
            "cover_edges = [(1, 2), (1, 3), (2, 3), (3, 4)]",
            "@assert partition_best_energy == 0",
            "@assert maxcut_best_energy == -7",
            "@assert cover_best_energy == 2",
            "@assert length(partition_optima) == 2",
            "@assert length(maxcut_optima) == 4",
            "@assert length(cover_optima) == 2",
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                assert_source_contains(self, source, marker)

        assert_source_excludes(self, source, "unsafe_backend")

        for out_of_scope_name in ("Qiskit", "OpenQAOA", "D-Wave", "token", "API key"):
            with self.subTest(out_of_scope_name=out_of_scope_name):
                assert_source_excludes(self, source, out_of_scope_name)

    def test_notebook_commits_reproducible_teaching_outputs(self) -> None:
        data = notebook()
        code_cells = [cell for cell in data["cells"] if cell["cell_type"] == "code"]
        populated_cells = [cell for cell in code_cells if cell.get("outputs", [])]

        self.assertTrue(code_cells)
        self.assertEqual(
            list(range(1, len(code_cells) + 1)),
            [cell.get("execution_count") for cell in code_cells],
        )
        self.assertGreaterEqual(len(populated_cells), 10)
        self.assertEqual([], notebook_cell(data, "bootstrap").get("outputs", []))
        self.assertEqual([], notebook_cell(data, "activate").get("outputs", []))

        expected_output_markers = {
            "partition-check": "imbalance=0, raw energy=0",
            "maxcut-check": "cut weight=7, raw energy=-7",
            "cover-check": "selected=[1, 3], uncovered=Tuple{Int64, Int64}[]",
            "solution-partition": "Best imbalance: 1",
            "solution-maxcut": "Best cut weight: 9",
            "solution-cover": "infeasible best-energy states include [[0, 0, 1, 0]]",
        }
        for cell_id, marker in expected_output_markers.items():
            with self.subTest(cell_id=cell_id):
                self.assertTrue(
                    marker in cell_output_text(notebook_cell(data, cell_id)),
                    f"Missing output marker in {cell_id!r}: {marker!r}",
                )

        plot_outputs = notebook_cell(data, "maxcut-plot").get("outputs", [])
        png_outputs = [
            output.get("data", {}).get("image/png", "") for output in plot_outputs
        ]
        self.assertTrue(any(len(image) > 1_000 for image in png_outputs))
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
        for marker in ("/home/", "/Users/", "C:\\Users", "AppData", "Bearer "):
            with self.subTest(forbidden_output_marker=marker):
                self.assertFalse(
                    marker in serialized_outputs,
                    f"Forbidden marker in committed outputs: {marker!r}",
                )

    def test_notebook_and_verifier_are_linked(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()
        makefile = (REPO_ROOT / "Makefile").read_text()

        self.assertIn("notebooks_jl/7-CanonicalProblems.ipynb", readme)
        self.assertIn("make verify-canonical-problems-julia", readme)
        self.assertIn("verify-canonical-problems-julia:", makefile)
        self.assertIn(
            'NOTEBOOKS="$(CANONICAL_PROBLEMS_JULIA_NOTEBOOK)"', makefile
        )


class CanonicalProblemsMathematicalInvariantTests(unittest.TestCase):
    def test_number_partitioning_expansion_and_decoded_optima(self) -> None:
        weights = (1, 3, 4, 8)
        total = sum(weights)

        def imbalance(bits: tuple[int, ...]) -> int:
            return sum(weight * (1 - 2 * bit) for weight, bit in zip(weights, bits))

        def expanded_energy(bits: tuple[int, ...]) -> int:
            constant = total**2
            linear = sum(
                (4 * weight**2 - 4 * total * weight) * bit
                for weight, bit in zip(weights, bits)
            )
            quadratic = sum(
                8 * weights[i] * weights[j] * bits[i] * bits[j]
                for i in range(len(weights))
                for j in range(i + 1, len(weights))
            )
            return constant + linear + quadratic

        states = binary_states(len(weights))
        self.assertTrue(
            all(expanded_energy(bits) == imbalance(bits) ** 2 for bits in states)
        )
        optimum = min(expanded_energy(bits) for bits in states)
        optima = {bits for bits in states if expanded_energy(bits) == optimum}

        self.assertEqual(0, optimum)
        self.assertEqual({(0, 0, 0, 1), (1, 1, 1, 0)}, optima)

    def test_max_cut_minimization_sign_and_decoded_optima(self) -> None:
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

        def qubo_energy(bits: tuple[int, ...]) -> int:
            return -sum(
                weight
                * (
                    bits[i - 1]
                    + bits[j - 1]
                    - 2 * bits[i - 1] * bits[j - 1]
                )
                for i, j, weight in weighted_edges
            )

        states = binary_states(4)
        self.assertTrue(all(qubo_energy(bits) == -cut_weight(bits) for bits in states))
        optimum = min(qubo_energy(bits) for bits in states)
        optima = {bits for bits in states if qubo_energy(bits) == optimum}

        self.assertEqual(-7, optimum)
        self.assertEqual(
            {
                (1, 0, 1, 0),
                (0, 1, 1, 0),
                (1, 0, 0, 1),
                (0, 1, 0, 1),
            },
            optima,
        )

    def test_vertex_cover_penalty_expansion_and_decoded_optima(self) -> None:
        edges = ((1, 2), (1, 3), (2, 3), (3, 4))
        penalty = 2
        degrees = [sum(vertex in edge for edge in edges) for vertex in range(1, 5)]

        def uncovered_edges(bits: tuple[int, ...]) -> int:
            return sum(bits[i - 1] == 0 and bits[j - 1] == 0 for i, j in edges)

        def application_energy(bits: tuple[int, ...]) -> int:
            return sum(bits) + penalty * uncovered_edges(bits)

        def expanded_energy(bits: tuple[int, ...]) -> int:
            constant = penalty * len(edges)
            linear = sum(
                (1 - penalty * degrees[i]) * bits[i] for i in range(len(bits))
            )
            quadratic = penalty * sum(
                bits[i - 1] * bits[j - 1] for i, j in edges
            )
            return constant + linear + quadratic

        states = binary_states(4)
        self.assertTrue(
            all(expanded_energy(bits) == application_energy(bits) for bits in states)
        )
        optimum = min(expanded_energy(bits) for bits in states)
        optima = {bits for bits in states if expanded_energy(bits) == optimum}

        self.assertEqual(2, optimum)
        self.assertEqual({(1, 0, 1, 0), (0, 1, 1, 0)}, optima)
        self.assertTrue(all(uncovered_edges(bits) == 0 for bits in optima))


if __name__ == "__main__":
    unittest.main()
