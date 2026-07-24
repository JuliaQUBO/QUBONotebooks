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


class AnnealingNotebookSourceTests(unittest.TestCase):
    def test_notebook_has_required_structure_and_primary_references(self) -> None:
        source = notebook_source()
        required_markers = (
            "## Setup",
            "## Learning objectives",
            "## Prerequisites",
            "## Simulated annealing concepts",
            "## One solver interface for five models",
            "## Seeded local comparison",
            "## Optional D-Wave QPU path",
            "## Practice checkpoints",
            "## Summary",
            "## References",
            "https://doi.org/10.1287/educ.2025.0288",
            "https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers",
            "https://docs.dwavequantum.com/",
            "original Julia code and prose",
            "quantum advantage",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_all_five_models_use_the_shared_runner(self) -> None:
        data = notebook()
        problem_source = "".join(notebook_cell(data, "problem-catalog")["source"])
        runner_source = "".join(notebook_cell(data, "annealing-runner")["source"])
        local_source = "".join(notebook_cell(data, "local-comparison")["source"])

        expected_problem_names = (
            "number partitioning",
            "weighted Max-Cut",
            "minimum vertex cover",
            "order partitioning",
            "cancer-genomics aggregate",
        )
        for name in expected_problem_names:
            with self.subTest(name=name):
                self.assertIn(f'name = "{name}"', problem_source)

        self.assertIn("function run_annealing(problem, config)", runner_source)
        self.assertIn("model, variables = problem.build_model()", runner_source)
        self.assertIn("set_optimizer(model, config.optimizer)", runner_source)
        self.assertIn("problem.decode(bits)", runner_source)
        self.assertIn("problem.energy(bits)", runner_source)
        self.assertIn("run_annealing(problem, local_config)", local_source)
        self.assertIn("for problem in annealing_problems", local_source)

    def test_default_local_path_is_seeded_neal_with_explicit_work(self) -> None:
        data = notebook()
        configuration = "".join(notebook_cell(data, "annealing-config")["source"])
        local_source = "".join(notebook_cell(data, "local-comparison")["source"])

        self.assertIn("DWave.Neal.Optimizer", configuration)
        self.assertIn('"num_reads" => LOCAL_READS', configuration)
        self.assertIn('"num_sweeps" => LOCAL_SWEEPS', configuration)
        self.assertIn('"seed" => LOCAL_SEED', configuration)
        self.assertIn('"beta_schedule_type" => "geometric"', configuration)
        self.assertIn("recomputed_energy", local_source)
        self.assertIn("reported_energy", local_source)
        self.assertIn("validated_states", local_source)

    def test_qpu_path_fails_closed_before_submission(self) -> None:
        data = notebook()
        imports_source = "".join(notebook_cell(data, "imports")["source"])
        guard_source = "".join(notebook_cell(data, "qpu-guard")["source"])
        qpu_source = "".join(notebook_cell(data, "qpu-run")["source"])
        full_source = notebook_source()

        self.assertIn('withenv("DWAVE_API_TOKEN" => nothing)', imports_source)
        self.assertIn("@eval using DWave", imports_source)
        self.assertIn("QUBONOTEBOOKS_ANNEALING_ENABLE_QPU", guard_source)
        self.assertIn('get(ENV, "DWAVE_API_TOKEN", "")', guard_source)
        self.assertIn("isempty(strip(token)) && error(", guard_source)
        self.assertIn("require_qpu_credentials()", qpu_source)
        self.assertIn("run_annealing(maxcut_problem, qpu_config)", qpu_source)
        self.assertIn("QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU", qpu_source)
        self.assertIn("qpu_hardware_submitted = false", qpu_source)
        self.assertIn(
            'qpu_hardware_submitted = qpu_result.execution_mode == "qpu"',
            qpu_source,
        )
        self.assertIn(
            "if qpu_hardware_required && !qpu_hardware_submitted",
            qpu_source,
        )
        self.assertIn(
            "D-Wave QPU verification was required, but no job was submitted.",
            qpu_source,
        )
        self.assertLess(
            qpu_source.index("require_qpu_credentials()"),
            qpu_source.index("run_annealing(maxcut_problem, qpu_config)"),
        )
        self.assertLess(
            qpu_source.index("run_annealing(maxcut_problem, qpu_config)"),
            qpu_source.index("qpu_hardware_submitted = qpu_result.execution_mode"),
        )
        self.assertLess(
            qpu_source.index("qpu_hardware_submitted = qpu_result.execution_mode"),
            qpu_source.index(
                "if qpu_hardware_required && !qpu_hardware_submitted"
            ),
        )
        self.assertIn("DWave.Optimizer", qpu_source)
        self.assertIn('"return_embedding" => true', qpu_source)
        self.assertNotIn("DWave.dwave_system", full_source)
        self.assertNotIn("PythonCall", full_source)
        self.assertNotIn("save_account", full_source)
        self.assertNotIn("solver=Dict", full_source)
        self.assertIsNone(re.search(r"\bAdvantage_system\d", full_source))
        self.assertIsNone(
            re.search(r'DWAVE_API_TOKEN\s*=\s*["\'][^"\']+["\']', full_source)
        )

    def test_qpu_metadata_and_plots_use_public_sanitized_interfaces(self) -> None:
        data = notebook()
        qpu_source = "".join(notebook_cell(data, "qpu-guard")["source"])
        qpu_source += "".join(notebook_cell(data, "qpu-run")["source"])
        plot_source = "".join(notebook_cell(data, "qpu-plots")["source"])

        self.assertIn("sanitized_qpu_metadata", qpu_source)
        self.assertIn('"qpu_access_time"', qpu_source)
        self.assertIn('"chain_strength"', qpu_source)
        self.assertIn('"embedding_parameters"', qpu_source)
        self.assertIn("DWave.WorkingGraph(qpu_result.metadata)", plot_source)
        self.assertIn("DWave.draw_topology", plot_source)
        self.assertIn("DWave.draw_embedding", plot_source)
        self.assertNotIn('"problem_id"', qpu_source)

    def test_qpu_result_is_included_in_credential_free_comparison_contract(
        self,
    ) -> None:
        data = notebook()
        runner_source = "".join(notebook_cell(data, "annealing-runner")["source"])
        table_source = "".join(notebook_cell(data, "comparison-table")["source"])
        qpu_source = "".join(notebook_cell(data, "qpu-run")["source"])

        self.assertIn("execution_mode = metadata", runner_source)
        self.assertIn("qpu_access_time_microseconds", runner_source)
        self.assertIn("function format_comparison_row(result)", table_source)
        self.assertIn("function print_comparison_table(results)", table_source)
        self.assertIn("qpu access μs", table_source)
        self.assertIn('execution_mode = "qpu"', table_source)
        self.assertIn("synthetic_qpu_row", table_source)
        self.assertIn(
            '@assert synthetic_qpu_row == "D-Wave QPU (synthetic)',
            table_source,
        )
        self.assertIn('"n/a | 0.250000 | 1234"', table_source)
        self.assertIn(
            "print_comparison_table((local_results[2], qpu_result))",
            qpu_source,
        )

    def test_small_models_use_exact_optima_and_cancer_claims_are_bounded(self) -> None:
        source = notebook_source()

        self.assertIn("exact_baseline", source)
        self.assertIn("exact_optimum_known = true", source)
        self.assertIn("exact_optimum_known = false", source)
        self.assertIn("success_probability", source)
        self.assertIn("not a proof of global optimality", source)
        self.assertIn("distinct_patient_bounds", source)
        self.assertIn("aggregate-only", source)

    def test_notebook_and_local_target_are_linked(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()
        makefile = (REPO_ROOT / "Makefile").read_text()
        julia_tests = (REPO_ROOT / "test" / "runtests.jl").read_text()
        verifier_tests = (REPO_ROOT / "tests" / "test_verify_notebooks.py").read_text()

        self.assertIn("notebooks_jl/11-Annealing.ipynb", readme)
        self.assertIn("make verify-annealing-julia-local", readme)
        self.assertIn("verify-annealing-julia-local:", makefile)
        self.assertIn('NOTEBOOKS="$(ANNEALING_JULIA_NOTEBOOK)"', makefile)
        self.assertIn('"notebooks_jl/11-Annealing.ipynb"', julia_tests)
        self.assertIn("ANNEALING_JULIA_NOTEBOOK_PATH", verifier_tests)


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


if __name__ == "__main__":
    unittest.main()
