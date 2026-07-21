from __future__ import annotations

import itertools
import json
import math
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "8-OrderPartitioning.ipynb"


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


ORDER_VALUES = (2, 3, 4, 5, 6, 8)
RISK_EXPOSURES = (
    (1, 1, 2, 5, 4, 5),
    (4, -2, 3, 6, -3, 0),
)


def value_imbalance(bits: tuple[int, ...]) -> int:
    return sum(
        value * (1 - 2 * bit) for value, bit in zip(ORDER_VALUES, bits)
    )


def risk_imbalances(bits: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(
        sum(exposure * (2 * bit - 1) for exposure, bit in zip(row, bits))
        for row in RISK_EXPOSURES
    )


def direct_energy(bits: tuple[int, ...], *, a: int = 2, b: int = 1) -> int:
    return a * value_imbalance(bits) ** 2 + b * sum(
        imbalance**2 for imbalance in risk_imbalances(bits)
    )


def expanded_energy(bits: tuple[int, ...], *, a: int = 2, b: int = 1) -> int:
    total_value = sum(ORDER_VALUES)
    constant = a * total_value**2
    linear = sum(
        a * (4 * value**2 - 4 * total_value * value) * bits[j]
        for j, value in enumerate(ORDER_VALUES)
    )
    quadratic = sum(
        8 * a * ORDER_VALUES[j] * ORDER_VALUES[k] * bits[j] * bits[k]
        for j in range(len(bits))
        for k in range(j + 1, len(bits))
    )

    for row in RISK_EXPOSURES:
        total_exposure = sum(row)
        constant += b * total_exposure**2
        linear += sum(
            b * (4 * exposure**2 - 4 * total_exposure * exposure) * bits[j]
            for j, exposure in enumerate(row)
        )
        quadratic += sum(
            8 * b * row[j] * row[k] * bits[j] * bits[k]
            for j in range(len(bits))
            for k in range(j + 1, len(bits))
        )

    return constant + linear + quadratic


class OrderPartitioningNotebookSourceTests(unittest.TestCase):
    def test_notebook_has_required_tutorial_structure_and_scope(self) -> None:
        source = notebook_source()
        required_markers = (
            "## Setup",
            "## Learning objectives",
            "## Prerequisites",
            "## Order-partitioning model",
            "## Exact verification",
            "## Decoded balances",
            "## Complement symmetry",
            "## Weight sensitivity",
            "## Practice checkpoints",
            "## Summary",
            "## References",
            "https://doi.org/10.1287/educ.2025.0288",
            "https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers",
            "not investment advice",
            "original Julia code",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

        for out_of_scope_marker in ("DWave", "QAOA", "API key", "token"):
            with self.subTest(out_of_scope_marker=out_of_scope_marker):
                self.assertNotIn(out_of_scope_marker, source)

    def test_model_places_each_square_outside_the_order_sum(self) -> None:
        data = notebook()
        model_source = "".join(notebook_cell(data, "qubo-model")["source"])

        grouped_square = (
            "(sum(risk_exposures[i, j] * (2 * order_x[j] - 1) "
            "for j in 1:n_orders))^2"
        )
        misplaced_square = "risk_exposures[i, j] * (2 * order_x[j] - 1)^2"

        self.assertIn(grouped_square, model_source)
        self.assertNotIn(misplaced_square, model_source)
        self.assertIn("incorrect_risk_term_square_inside", notebook_source())

    def test_notebook_uses_public_local_exact_solver_and_exhaustive_checks(self) -> None:
        source = notebook_source()
        required_markers = (
            "QUBO.ExactSampler.Optimizer",
            "all_binary_states(n_orders)",
            "evaluate_jump_objective",
            "order_partitioning_energy",
            "length(states) == 64",
            "length(unique(correct_risk_terms)) > 1",
            "length(unique(incorrect_risk_terms)) == 1",
            "same_states(exact_optima, enumerated_optima)",
            "complement_bits",
            "decoded_metrics",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_notebook_commits_reproducible_outputs(self) -> None:
        data = notebook()
        code_cells = [cell for cell in data["cells"] if cell["cell_type"] == "code"]

        self.assertTrue(code_cells)
        self.assertEqual(
            list(range(1, len(code_cells) + 1)),
            [cell.get("execution_count") for cell in code_cells],
        )
        self.assertEqual([], notebook_cell(data, "bootstrap").get("outputs", []))
        self.assertEqual([], notebook_cell(data, "activate").get("outputs", []))

        expected_output_markers = {
            "all-state-check": "All 64 assignments match the direct grouped-square formula.",
            "exact-check": "Enumerated optimum energy: 28",
            "decoded-balance": "Group A total: $1.5M",
            "complement-check": "Complement energy: 28",
            "weight-sensitivity": "risk priority",
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
        for marker in ("/home/", "/Users/", "C:\\Users", "AppData", "Bearer "):
            with self.subTest(forbidden_output_marker=marker):
                self.assertNotIn(marker, serialized_outputs)

    def test_notebook_and_target_are_linked(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()
        makefile = (REPO_ROOT / "Makefile").read_text()

        self.assertIn("notebooks_jl/8-OrderPartitioning.ipynb", readme)
        self.assertIn("make verify-order-partitioning-julia", readme)
        self.assertIn("verify-order-partitioning-julia:", makefile)
        self.assertIn(
            'NOTEBOOKS="$(ORDER_PARTITIONING_JULIA_NOTEBOOK)"', makefile
        )


class OrderPartitioningMathematicalInvariantTests(unittest.TestCase):
    def test_expanded_qubo_matches_direct_formula_for_all_assignments(self) -> None:
        states = binary_states(len(ORDER_VALUES))

        self.assertEqual(64, len(states))
        self.assertTrue(
            all(expanded_energy(bits) == direct_energy(bits) for bits in states)
        )

    def test_risk_regression_and_complement_symmetry(self) -> None:
        states = binary_states(len(ORDER_VALUES))
        correct_risk_terms = {
            sum(imbalance**2 for imbalance in risk_imbalances(bits))
            for bits in states
        }
        misplaced_square_terms = {
            sum(
                exposure * (2 * bit - 1) ** 2
                for row in RISK_EXPOSURES
                for exposure, bit in zip(row, bits)
            )
            for bits in states
        }

        self.assertGreater(len(correct_risk_terms), 1)
        self.assertEqual(1, len(misplaced_square_terms))
        self.assertTrue(
            all(
                direct_energy(bits)
                == direct_energy(tuple(1 - bit for bit in bits))
                for bits in states
            )
        )

    def test_exact_optimum_and_decoded_metrics(self) -> None:
        states = binary_states(len(ORDER_VALUES))
        optimum = min(direct_energy(bits) for bits in states)
        optima = {bits for bits in states if direct_energy(bits) == optimum}

        self.assertEqual(28, optimum)
        self.assertEqual(
            {(0, 0, 0, 1, 0, 1), (1, 1, 1, 0, 1, 0)}, optima
        )

        representative = (0, 0, 0, 1, 0, 1)
        group_a = [j for j, bit in enumerate(representative) if bit == 0]
        group_b = [j for j, bit in enumerate(representative) if bit == 1]
        value_a = sum(ORDER_VALUES[j] for j in group_a)
        value_b = sum(ORDER_VALUES[j] for j in group_b)
        risk_a = tuple(sum(row[j] for j in group_a) for row in RISK_EXPOSURES)
        risk_b = tuple(sum(row[j] for j in group_b) for row in RISK_EXPOSURES)

        self.assertEqual((15, 13), (value_a, value_b))
        self.assertEqual((8, 2), risk_a)
        self.assertEqual((10, 6), risk_b)
        self.assertEqual((2, 4), risk_imbalances(representative))
        self.assertTrue(math.isclose(math.sqrt(20), math.dist(risk_a, risk_b)))

    def test_weight_sensitivity_exposes_the_tradeoff(self) -> None:
        states = binary_states(len(ORDER_VALUES))

        def optima(a: int, b: int) -> tuple[int, set[tuple[int, ...]]]:
            best = min(direct_energy(bits, a=a, b=b) for bits in states)
            return best, {
                bits for bits in states if direct_energy(bits, a=a, b=b) == best
            }

        value_energy, value_optima = optima(8, 1)
        risk_energy, risk_optima = optima(1, 8)

        self.assertEqual(40, value_energy)
        self.assertEqual(
            {(0, 1, 0, 1, 1, 0), (1, 0, 1, 0, 0, 1)}, value_optima
        )
        self.assertTrue(all(value_imbalance(bits) == 0 for bits in value_optima))

        self.assertEqual(68, risk_energy)
        self.assertEqual(
            {(0, 0, 0, 1, 1, 0), (1, 1, 1, 0, 0, 1)}, risk_optima
        )
        self.assertTrue(
            all(sum(value**2 for value in risk_imbalances(bits)) == 4 for bits in risk_optima)
        )


if __name__ == "__main__":
    unittest.main()
