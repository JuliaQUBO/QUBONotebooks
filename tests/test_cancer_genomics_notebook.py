from __future__ import annotations

import csv
import itertools
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "9-CancerGenomics.ipynb"
DATA_DIR = REPO_ROOT / "notebooks_data"


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


TINY_B = (
    (1, 1, 0, 0),
    (1, 0, 0, 0),
    (1, 0, 0, 0),
    (0, 1, 0, 0),
    (0, 0, 1, 1),
    (0, 0, 1, 0),
    (0, 0, 0, 1),
)


def coverage_and_comutation(
    incidence: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], tuple[tuple[int, ...], ...]]:
    gene_count = len(incidence[0])
    coverage = tuple(sum(row[j] for row in incidence) for j in range(gene_count))
    matrix = [[0] * gene_count for _ in range(gene_count)]

    for i in range(gene_count - 1):
        for j in range(i + 1, gene_count):
            overlap = sum(row[i] * row[j] for row in incidence)
            matrix[i][j] = overlap
            matrix[j][i] = overlap

    return coverage, tuple(tuple(row) for row in matrix)


TINY_COVERAGE, TINY_A = coverage_and_comutation(TINY_B)


def pathway_energy(bits: tuple[int, ...], *, alpha: float) -> float:
    pairwise = sum(
        TINY_A[i][j] * bits[i] * bits[j]
        for i in range(len(bits))
        for j in range(i + 1, len(bits))
    )
    coverage_reward = sum(value * bit for value, bit in zip(TINY_COVERAGE, bits))
    return 2 * pairwise - alpha * coverage_reward


def selected_metrics(
    coverage: tuple[int, ...],
    matrix: tuple[tuple[int, ...], ...],
    bits: tuple[int, ...],
    *,
    patient_count: int,
) -> dict:
    selected = tuple(i for i, bit in enumerate(bits) if bit)
    coverage_sum = sum(coverage[i] for i in selected)
    pairwise = sum(matrix[i][j] for i in selected for j in selected if i < j)
    if selected:
        lower = max(max(coverage[i] for i in selected), coverage_sum - pairwise)
        upper = min(patient_count, coverage_sum)
    else:
        lower = upper = 0
    pair_count = len(selected) * (len(selected) - 1) // 2
    zero_pairs = sum(
        matrix[i][j] == 0 for i in selected for j in selected if i < j
    )

    return {
        "selected": selected,
        "coverage_sum": coverage_sum,
        "pairwise": pairwise,
        "double_counted": 2 * pairwise,
        "bounds": (lower, upper),
        "zero_pair_fraction": None if pair_count == 0 else zero_pairs / pair_count,
    }


class CancerGenomicsNotebookSourceTests(unittest.TestCase):
    def test_notebook_has_required_tutorial_structure_and_references(self) -> None:
        source = notebook_source()
        required_markers = (
            "## Setup",
            "## Learning objectives",
            "## Prerequisites",
            "## From incidence data to coverage and co-mutation",
            "## Build and interpret the QUBO",
            "## Exhaustive validation on the tiny fixture",
            "## Decode pathway metrics safely",
            "## Provenance-checked TCGA AML aggregate",
            "## Practice checkpoints",
            "## Summary",
            "## References",
            "https://doi.org/10.1287/educ.2025.0288",
            "https://doi.org/10.1101/845719",
            "https://doi.org/10.1056/NEJMoa1301689",
            "https://www.cbioportal.org/",
            "https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers",
            "original Julia code and prose",
            "not a clinically validated pathway",
            "not medical guidance",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_pair_construction_and_double_counting_are_explicit(self) -> None:
        data = notebook()
        construction = "".join(notebook_cell(data, "matrix-helpers")["source"])
        formula = "".join(notebook_cell(data, "metric-helpers")["source"])
        all_state_check = "".join(notebook_cell(data, "all-state-check")["source"])

        self.assertIn("for i in 1:(n_genes - 1)", construction)
        self.assertIn("for j in (i + 1):n_genes", construction)
        self.assertIn("A[i, j] = overlap", construction)
        self.assertIn("A[j, i] = overlap", construction)
        self.assertNotIn("if i != j", construction)
        self.assertIn("dot(bits, A * bits)", formula)
        self.assertIn(
            "double_counted_comutation == 2 * pairwise_comutation",
            formula,
        )
        self.assertIn("tiny_pair_expansion_energies", all_state_check)
        self.assertIn("2 * sum(", all_state_check)

    def test_decoding_handles_empty_and_aggregate_only_paths(self) -> None:
        data = notebook()
        helpers = "".join(notebook_cell(data, "metric-helpers")["source"])
        empty_check = "".join(notebook_cell(data, "empty-decode")["source"])
        aggregate_limits = "".join(notebook_cell(data, "aggregate-limits")["source"])

        self.assertIn("pair_count == 0 ? missing", helpers)
        self.assertIn("isempty(selected) && return (lower = 0, upper = 0)", helpers)
        self.assertIn("exact_unique_coverage = missing", helpers)
        self.assertIn("Bonferroni", helpers)
        self.assertIn("ismissing(tiny_empty_metrics.zero_comutation_pair_fraction)", empty_check)
        self.assertIn("triple and higher intersections", aggregate_limits)
        self.assertIn("avoids fabricating a distinct-patient count", aggregate_limits)

    def test_full_run_is_seeded_local_and_validates_every_returned_state(self) -> None:
        data = notebook()
        sampler = "".join(notebook_cell(data, "sampler-helper")["source"])
        run = "".join(notebook_cell(data, "aggregate-samples")["source"])
        source = notebook_source()

        for marker in (
            "set_optimizer(model, DWave.Neal.Optimizer)",
            'set_optimizer_attribute(model, "num_reads", num_reads)',
            'set_optimizer_attribute(model, "num_sweeps", num_sweeps)',
            'set_optimizer_attribute(model, "seed", seed)',
            "for result in 1:result_count(model)",
            "reported_energy",
            "recomputed_energy",
            "validate_decoded_metrics",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, sampler)

        self.assertIn("returned_states == result.validated_states", run)
        self.assertIn("length(unique(result.pathway_size", run)
        self.assertIn("length(unique(Tuple(result.bits)", run)
        self.assertNotIn("@assert result.genes", run)
        self.assertNotIn("@assert result.bits", run)
        self.assertIn("not proofs of global optimality", source)

        for forbidden in (
            "DWave.Optimizer",
            "save_account",
            "Downloads.download",
            "HTTP.get",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

        imports = "".join(notebook_cell(data, "imports")["source"])
        bootstrap = (
            REPO_ROOT / "scripts" / "notebook_bootstrap.jl"
        ).read_text()
        self.assertIn("warm_notebook_packages!", imports)
        self.assertIn('"9-CancerGenomics"', imports)
        self.assertIn('withenv("DWAVE_API_TOKEN" => nothing)', bootstrap)
        self.assertIn('"9-CancerGenomics" => :(using DWave', bootstrap)
        self.assertNotIn('get(ENV, "DWAVE_API_TOKEN"', source)

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
            "tiny-matrices": "D diagonal = [3, 2, 2, 2]",
            "all-state-check": "All 16 assignments match",
            "exact-check": "Enumerated optimum energy: -3.75",
            "tiny-decode": "distinct-patient coverage: 5",
            "empty-decode": "Empty pathway decoded safely",
            "load-aggregate": "Loaded 33 genes for 196 aggregate patients",
            "aggregate-samples": "Seeded local Neal sampler",
            "solution-double-count": "symmetric matrix energy",
            "solution-alpha": "Tiny optimum sizes",
            "solution-bounds": "incidence-derived exact union",
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
        julia_tests = (REPO_ROOT / "test" / "runtests.jl").read_text()
        verifier_tests = (REPO_ROOT / "tests" / "test_verify_notebooks.py").read_text()

        self.assertIn("notebooks_jl/9-CancerGenomics.ipynb", readme)
        self.assertIn("make verify-cancer-genomics-julia", readme)
        self.assertIn("verify-cancer-genomics-julia:", makefile)
        self.assertIn('NOTEBOOKS="$(CANCER_GENOMICS_JULIA_NOTEBOOK)"', makefile)
        self.assertIn('"notebooks_jl/9-CancerGenomics.ipynb"', julia_tests)
        self.assertIn("CANCER_GENOMICS_JULIA_NOTEBOOK_PATH", verifier_tests)


class CancerGenomicsMathematicalInvariantTests(unittest.TestCase):
    def test_fixture_derives_known_coverage_and_symmetric_matrix(self) -> None:
        self.assertEqual((3, 2, 2, 2), TINY_COVERAGE)
        self.assertEqual(
            (
                (0, 1, 0, 0),
                (1, 0, 0, 0),
                (0, 0, 0, 1),
                (0, 0, 1, 0),
            ),
            TINY_A,
        )
        self.assertTrue(all(TINY_A[i][i] == 0 for i in range(4)))
        self.assertTrue(
            all(TINY_A[i][j] == TINY_A[j][i] for i in range(4) for j in range(4))
        )
        self.assertTrue(
            all(
                TINY_A[i][j] <= min(TINY_COVERAGE[i], TINY_COVERAGE[j])
                for i in range(4)
                for j in range(4)
            )
        )

    def test_explicit_pair_energy_matches_matrix_convention_for_all_states(self) -> None:
        for bits in binary_states(4):
            matrix_energy = sum(
                bits[i] * TINY_A[i][j] * bits[j]
                for i in range(4)
                for j in range(4)
            ) - 0.75 * sum(
                value * bit for value, bit in zip(TINY_COVERAGE, bits)
            )
            with self.subTest(bits=bits):
                self.assertEqual(pathway_energy(bits, alpha=0.75), matrix_energy)

        states = binary_states(4)
        best = min(pathway_energy(bits, alpha=0.75) for bits in states)
        optima = {bits for bits in states if pathway_energy(bits, alpha=0.75) == best}
        self.assertEqual(-3.75, best)
        self.assertEqual({(1, 0, 1, 0), (1, 0, 0, 1)}, optima)

    def test_alpha_changes_complete_tiny_optimum_sizes(self) -> None:
        states = binary_states(4)

        def optimum_sizes(alpha: float) -> set[int]:
            best = min(pathway_energy(bits, alpha=alpha) for bits in states)
            return {
                sum(bits)
                for bits in states
                if pathway_energy(bits, alpha=alpha) == best
            }

        self.assertEqual({2}, optimum_sizes(0.5))
        self.assertEqual({4}, optimum_sizes(1.5))

    def test_empty_metrics_are_safe_and_union_bounds_contain_exact_value(self) -> None:
        empty = selected_metrics(TINY_COVERAGE, TINY_A, (0, 0, 0, 0), patient_count=7)
        self.assertEqual((), empty["selected"])
        self.assertEqual(0, empty["coverage_sum"])
        self.assertEqual(0, empty["pairwise"])
        self.assertEqual((0, 0), empty["bounds"])
        self.assertIsNone(empty["zero_pair_fraction"])

        selected = (1, 1, 1, 0)
        metrics = selected_metrics(TINY_COVERAGE, TINY_A, selected, patient_count=7)
        exact_union = sum(
            any(row[j] and selected[j] for j in range(4)) for row in TINY_B
        )
        self.assertEqual((6, 7), metrics["bounds"])
        self.assertEqual(6, exact_union)
        self.assertLessEqual(metrics["bounds"][0], exact_union)
        self.assertLessEqual(exact_union, metrics["bounds"][1])

    def test_committed_artifact_matches_notebook_input_contract(self) -> None:
        with (DATA_DIR / "9-CancerGenomics_coverage.csv").open(newline="") as handle:
            coverage_rows = list(csv.DictReader(handle))
        with (DATA_DIR / "9-CancerGenomics_comutation.csv").open(newline="") as handle:
            matrix_rows = list(csv.reader(handle))
        provenance = json.loads(
            (DATA_DIR / "9-CancerGenomics_provenance.json").read_text()
        )

        genes = [row["gene"] for row in coverage_rows]
        coverage = [int(row["patient_count"]) for row in coverage_rows]
        matrix = [[int(value) for value in row[1:]] for row in matrix_rows[1:]]

        self.assertEqual(33, len(genes))
        self.assertEqual(33, provenance["aggregate"]["selected_gene_count"])
        self.assertEqual(196, provenance["aggregate"]["patient_count"])
        self.assertEqual(["gene", *genes], matrix_rows[0])
        self.assertEqual(33, len(matrix))
        for i in range(33):
            self.assertEqual(0, matrix[i][i])
            for j in range(33):
                self.assertEqual(matrix[i][j], matrix[j][i])
                self.assertLessEqual(matrix[i][j], min(coverage[i], coverage[j]))


if __name__ == "__main__":
    unittest.main()
