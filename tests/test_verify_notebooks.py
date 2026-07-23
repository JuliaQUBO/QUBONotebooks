from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_notebooks.py"
MATHPROG_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "1-MathProg.ipynb"
QUBO_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "2-QUBO.ipynb"
QUBO_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "2-QUBO_python.ipynb"
GAMA_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "3-GAMA.ipynb"
GAMA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "3-GAMA_python.ipynb"
DWAVE_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "4-DWave.ipynb"
DWAVE_PYTHON_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "4-DWAVE_python.ipynb"
MATHPROG_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "1-MathProg_python.ipynb"
QCI_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "6-QCi_python.ipynb"
BENCHMARKING_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "5-Benchmarking.ipynb"
BENCHMARKING_PYTHON_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_py" / "5-Benchmarking_python.ipynb"
)
CANONICAL_PROBLEMS_JULIA_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_jl" / "7-CanonicalProblems.ipynb"
)
ORDER_PARTITIONING_JULIA_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_jl" / "8-OrderPartitioning.ipynb"
)
CANCER_GENOMICS_JULIA_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_jl" / "9-CancerGenomics.ipynb"
)
QAOA_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "10-QAOA.ipynb"
ANNEALING_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "11-Annealing.ipynb"
BENCHMARKING_RESULTS_ARCHIVES = (
    REPO_ROOT / "notebooks_py" / "results.zip",
    REPO_ROOT / "notebooks_jl" / "results.zip",
)
JULIA_COLAB_NOTEBOOK_PATHS = (
    REPO_ROOT / "notebooks_jl" / "1-MathProg.ipynb",
    REPO_ROOT / "notebooks_jl" / "2-QUBO.ipynb",
    REPO_ROOT / "notebooks_jl" / "3-GAMA.ipynb",
    REPO_ROOT / "notebooks_jl" / "4-DWave.ipynb",
    REPO_ROOT / "notebooks_jl" / "5-Benchmarking.ipynb",
    CANONICAL_PROBLEMS_JULIA_NOTEBOOK_PATH,
    ORDER_PARTITIONING_JULIA_NOTEBOOK_PATH,
    CANCER_GENOMICS_JULIA_NOTEBOOK_PATH,
    QAOA_JULIA_NOTEBOOK_PATH,
    ANNEALING_JULIA_NOTEBOOK_PATH,
)
BOOTSTRAP_PATH = REPO_ROOT / "scripts" / "notebook_bootstrap.jl"
NOTEBOOK_DIRS = (
    REPO_ROOT / "notebooks_jl",
    REPO_ROOT / "notebooks_py",
)
NOTEBOOK_REFERENCE_HEADING = re.compile(r"^#+\s+references\b", re.IGNORECASE)
GAMA_DATA_FILES = (
    REPO_ROOT / "notebooks_data" / "3-GAMA_example4_coefficients.csv",
    REPO_ROOT / "notebooks_data" / "3-GAMA_example4_feasible_starts.csv",
)
SPEC = importlib.util.spec_from_file_location("verify_notebooks", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
verify_notebooks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_notebooks)


def notebook_source(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def notebook_output_text(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join(
        json.dumps(cell.get("outputs", []), ensure_ascii=False)
        for cell in notebook["cells"]
    )


def notebook_cell_source(path: Path, marker: str) -> str:
    notebook = json.loads(path.read_text())

    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if marker in source:
            return source

    raise AssertionError(f"Could not find notebook cell containing {marker!r}")


def notebook_function_source(path: Path, function_name: str) -> str:
    cell_source = notebook_cell_source(path, f"def {function_name}(")
    function_start = cell_source.index(f"def {function_name}(")
    next_function = cell_source.find("\ndef ", function_start + 1)
    if next_function == -1:
        return cell_source[function_start:]
    return cell_source[function_start:next_function]


def notebook_cell_sources(path: Path) -> list[str]:
    notebook = json.loads(path.read_text())
    return ["".join(cell.get("source", [])) for cell in notebook["cells"]]


def notebook_cells(path: Path) -> list[dict]:
    notebook = json.loads(path.read_text())
    return notebook["cells"]


def notebook_solution_output_texts(path: Path) -> list[str]:
    outputs = []

    for cell in notebook_cells(path):
        source = "".join(cell.get("source", []))
        if (
            cell.get("cell_type") == "code"
            and "# SOLUTION (hidden in workshop version):" in source
        ):
            stream_text = []
            for output in cell.get("outputs", []):
                if (
                    output.get("output_type") == "stream"
                    and output.get("name") == "stdout"
                ):
                    text = output.get("text", [])
                    stream_text.append("".join(text) if isinstance(text, list) else text)
            outputs.append("".join(stream_text))

    return outputs


def notebook_paths() -> list[Path]:
    return sorted(path for directory in NOTEBOOK_DIRS for path in directory.glob("*.ipynb"))


def notebook_first_heading(cell: dict) -> str:
    source = "".join(cell.get("source", []))

    for line in source.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped

    return ""


class NotebookSourceSafetyTests(unittest.TestCase):
    def test_notebooks_do_not_use_jump_unsafe_backend(self) -> None:
        offenders = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in notebook_paths()
            if "unsafe_backend" in notebook_source(path)
        ]

        self.assertEqual([], offenders)

    def test_julia_qubo_color_plot_qualifies_jump_backend(self) -> None:
        source = notebook_cell_source(
            QUBO_JULIA_NOTEBOOK_PATH,
            "EnergyFrequencyPlot(QUBOTools.solution(JuMP.backend",
        )

        self.assertIn("JuMP.backend(color_model).optimizer", source)
        self.assertNotIn("solution(backend(color_model)", source)

    def test_notebook_outputs_do_not_contain_personal_paths(self) -> None:
        personal_path_patterns = (
            "C:\\Users",
            "AppData",
            "purdue-internship",
            "QUBONotebooksFork",
            "home/azain",
        )
        offenders = [
            (path.relative_to(REPO_ROOT).as_posix(), pattern)
            for path in notebook_paths()
            for pattern in personal_path_patterns
            if pattern in notebook_output_text(path)
        ]

        self.assertEqual([], offenders)

    def test_notebook_outputs_do_not_contain_python_invalid_escape_warnings(self) -> None:
        offenders = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in notebook_paths()
            if "SyntaxWarning: invalid escape sequence" in notebook_output_text(path)
        ]

        self.assertEqual([], offenders)

    def test_julia_notebooks_filter_python_invalid_escape_warnings(self) -> None:
        filter_text = "ignore:invalid escape sequence:SyntaxWarning"
        dwave_import_markers = ("using DWave", "import DWave", "@eval using DWave")

        for path in JULIA_COLAB_NOTEBOOK_PATHS:
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                source = notebook_source(path)

                self.assertIn(filter_text, source)

                dwave_import_indexes = [
                    source.index(marker)
                    for marker in dwave_import_markers
                    if marker in source
                ]
                if dwave_import_indexes:
                    self.assertLess(source.index(filter_text), min(dwave_import_indexes))


class QUBONotebookConsistencyTests(unittest.TestCase):
    def test_julia_qubo_problem_statement_uses_julia_indices(self) -> None:
        source = notebook_cell_source(
            QUBO_JULIA_NOTEBOOK_PATH,
            "Suppose we want to solve the following problem via QUBO",
        )

        self.assertIn(
            "2x_1+4x_2+4x_3+4x_4+4x_5+4x_6+"
            "5x_7+4x_8+5x_9+6x_{10}+5x_{11}",
            source,
        )
        self.assertNotIn("x_0", source)

    def test_julia_qubo_documented_optima_match_problem_data(self) -> None:
        rows = (
            (1, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1),
            (0, 1, 0, 1, 0, 1, 1, 0, 1, 1, 1),
            (0, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1),
        )
        b = (1, 1, 1)
        c = (2, 4, 4, 4, 4, 4, 5, 4, 5, 6, 5)
        feasible_singletons = [
            index
            for index, column in enumerate(zip(*rows), start=1)
            if column == b
        ]
        best_singletons = [
            index
            for index in feasible_singletons
            if c[index - 1] == min(c[j - 1] for j in feasible_singletons)
        ]
        source = notebook_cell_source(
            QUBO_JULIA_NOTEBOOK_PATH,
            "optimal solution of this problem",
        )

        self.assertEqual([9, 11], best_singletons)
        self.assertIn("$x_{9} = 1", source)
        self.assertIn("$x_{11} = 1", source)
        self.assertNotIn("$x_{10} = 1", source)

    def test_ising_matrix_display_matches_coupling_definitions(self) -> None:
        corrected_first_row = (
            "0 & 0 & 0 & 24 & 24 & 24 & 0 & 24 & 24 & 24 & 24\\\\"
        )
        stale_first_row = (
            "0 & 0 & 0 & 24 & 24 & 24 & 24 & 24 & 24 & 24 & 24\\\\"
        )

        for path in (QUBO_JULIA_NOTEBOOK_PATH, QUBO_NOTEBOOK_PATH):
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                source = notebook_cell_source(path, "J = \\begin{bmatrix}")

                self.assertIn(corrected_first_row, source)
                self.assertNotIn(stale_first_row, source)

    def test_julia_qubo_cells_use_distinct_x_bindings(self) -> None:
        source = notebook_source(QUBO_JULIA_NOTEBOOK_PATH)

        self.assertIn(
            '@variable(qubo_model, x_qubo[1:11], Bin, base_name = "x")',
            source,
        )
        self.assertIn(
            '@variable(qubo_ilp_model, x_qubo_ilp[1:11], Bin, base_name = "x")',
            source,
        )
        self.assertIn(
            '@variable(ising_ilp_model, x_ising_ilp[1:n], Bin, base_name = "x")',
            source,
        )
        self.assertNotIn("x = qubo_model[:x]", source)
        self.assertNotIn("value.(x))", source)

    def test_python_pyomo_indices_do_not_overwrite_ising_couplings(self) -> None:
        source = notebook_source(QUBO_NOTEBOOK_PATH)

        self.assertIn("# Ising coupling matrix (J_{ij})\nJ = {(0, 3): 24.0", source)
        self.assertIn(
            "J_idx = range(len(h))  # Pyomo index set for Ising couplings",
            source,
        )
        self.assertIn(
            "model_ising_pyo.y = pyo.Var(I, J_idx, domain=pyo.Binary)",
            source,
        )
        self.assertNotIn("J = range", source)


class NotebookTextAccuracyTests(unittest.TestCase):
    def test_python_mathprog_objective_comment_matches_code(self) -> None:
        source = notebook_source(MATHPROG_NOTEBOOK_PATH)

        self.assertIn("# Objective: max 5.5*x1 + 2.1*x2", source)
        self.assertNotIn("Z = 5.5*x1 + 2.1*x2", source)
        self.assertIn("objective_heatmap = np.fromfunction", source)
        self.assertNotIn("min 7.3x1", source)

    def test_python_mathprog_feasible_region_removal_is_guarded(self) -> None:
        source = notebook_source(MATHPROG_NOTEBOOK_PATH)

        self.assertEqual(2, source.count("feas_reg.remove()"))
        self.assertEqual(2, source.count("try:\n    feas_reg.remove()"))
        self.assertEqual(
            2,
            source.count("except (ValueError, AttributeError, NameError):"),
        )

    def test_python_notebooks_do_not_have_reported_text_artifacts(self) -> None:
        banned_strings = (
            "Quantum annealiing",
            "Binary Quandratic model",
            "coefficeints",
            "follwing",
            "Qudratic",
            "Offse term",
            "# doctest: +SKIP",
            "Julia's built-in data structures",
        )
        offenders = [
            (path.relative_to(REPO_ROOT).as_posix(), text)
            for path in (QUBO_NOTEBOOK_PATH, QCI_NOTEBOOK_PATH)
            for text in banned_strings
            if text in notebook_source(path)
        ]

        self.assertEqual([], offenders)

    def test_julia_notebooks_do_not_have_reported_text_artifacts(self) -> None:
        banned_strings = (
            "INCLP",
            "colobar",
            "yective function",
            "Finally, for we will use Graphs.jl",
        )
        offenders = [
            (path.relative_to(REPO_ROOT).as_posix(), text)
            for path in (
                MATHPROG_JULIA_NOTEBOOK_PATH,
                QUBO_JULIA_NOTEBOOK_PATH,
                GAMA_JULIA_NOTEBOOK_PATH,
            )
            for text in banned_strings
            if text in notebook_source(path)
        ]

        self.assertEqual([], offenders)

    def test_julia_benchmarking_explains_ising_model_before_packages(self) -> None:
        source = notebook_cell_source(BENCHMARKING_JULIA_NOTEBOOK_PATH, "## Ising model")

        self.assertIn("binary spin variables", source)
        self.assertIn("minimum-energy spin assignment", source)
        self.assertIn("common benchmark for simulated annealing", source)
        self.assertLess(source.index("binary spin variables"), source.index("JuMP"))


class NotebookMaintenanceIssueTests(unittest.TestCase):
    def test_student_facing_slide_placeholders_are_removed(self) -> None:
        offenders = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in notebook_paths()
            if "Let's go back to the slides" in notebook_source(path)
            or " in the slides" in notebook_source(path)
        ]

        self.assertEqual([], offenders)

    def test_penalty_rationale_is_documented_before_rho_computation(self) -> None:
        for path in (
            QUBO_NOTEBOOK_PATH,
            DWAVE_PYTHON_NOTEBOOK_PATH,
            QCI_NOTEBOOK_PATH,
            QUBO_JULIA_NOTEBOOK_PATH,
            DWAVE_JULIA_NOTEBOOK_PATH,
        ):
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cells(path)
                sources = ["".join(cell.get("source", [])) for cell in cells]
                explanation_index = next(
                    index
                    for index, source in enumerate(sources)
                    if "### Penalty parameter rationale" in source
                )
                rho_index = next(
                    index
                    for index, cell in enumerate(cells)
                    if cell.get("cell_type") == "code"
                    and (
                        "rho =" in "".join(cell.get("source", []))
                        or "ρ =" in "".join(cell.get("source", []))
                    )
                )
                explanation = sources[explanation_index]

                self.assertLess(explanation_index, rho_index)
                self.assertIn("rho = sum(abs(c)) + epsilon", explanation)
                self.assertIn("Worked example", explanation)
                self.assertIn("Glover, Kochenberger, and Du (2019)", explanation)

    def test_python_benchmarking_uses_supported_dimod_graph_helper(self) -> None:
        source = notebook_source(BENCHMARKING_PYTHON_NOTEBOOK_PATH)

        self.assertIn("dimod.to_networkx_graph(model_ising)", source)
        self.assertIn("dimod.to_networkx_graph(model_random)", source)
        self.assertNotIn("model_ising.to_networkx_graph()", source)
        self.assertNotIn("model_random.to_networkx_graph()", source)

    def test_python_benchmarking_random_weights_match_documented_distribution(self) -> None:
        source = notebook_source(BENCHMARKING_PYTHON_NOTEBOOK_PATH)

        self.assertIn("J = 2 * np.random.rand(N, N) - 1", source)
        self.assertIn("h = 2 * np.random.rand(N) - 1", source)
        self.assertNotIn("J = np.random.rand(N,N)", source)
        self.assertNotIn("h = np.random.rand(N)", source)

    def test_python_benchmarking_long_run_warns_and_saves_partial_results(self) -> None:
        source = notebook_source(BENCHMARKING_PYTHON_NOTEBOOK_PATH)

        self.assertIn("Warning - long-running computation", source)
        self.assertIn("20 instances x 320 sweep values x 1000 reads", source)
        self.assertIn("from tqdm.auto import tqdm", source)
        self.assertIn('for instance in tqdm(instances, desc="Instances"):', source)
        self.assertIn(
            "for sweep in tqdm(sweeps, desc=f\"Instance {instance} sweeps\", leave=False):",
            source,
        )
        self.assertGreaterEqual(
            source.count("save_benchmark_cache(all_results_json_name, all_results)"),
            2,
        )

    def test_qci_small_qubo_uses_solver_free_enumeration(self) -> None:
        source = notebook_source(QCI_NOTEBOOK_PATH)

        self.assertIn("import itertools", source)
        self.assertIn("itertools.product([0, 1], repeat=2)", source)
        self.assertIn("simple_qubo_energy", source)
        self.assertNotIn("pyo.SolverFactory('bonmin')", source)
        self.assertNotIn('"bonmin"', source)
        self.assertNotIn("'bonmin'", source)

    def test_reported_unused_imports_are_removed(self) -> None:
        checks = (
            (MATHPROG_NOTEBOOK_PATH, "import sys"),
            (QUBO_NOTEBOOK_PATH, "from scipy.special import gamma"),
            (QUBO_NOTEBOOK_PATH, "import math"),
            (QUBO_NOTEBOOK_PATH, "from itertools import chain"),
            (QUBO_NOTEBOOK_PATH, "import time"),
            (GAMA_NOTEBOOK_PATH, "from sympy import *"),
            (DWAVE_PYTHON_NOTEBOOK_PATH, "from scipy.special import gamma"),
            (QCI_NOTEBOOK_PATH, "from scipy.special import gamma"),
        )

        offenders = [
            (path.relative_to(REPO_ROOT).as_posix(), text)
            for path, text in checks
            if text in notebook_source(path)
        ]

        self.assertEqual([], offenders)

    def test_julia_dwave_kernel_and_imports_match_series(self) -> None:
        mathprog_metadata = json.loads(MATHPROG_JULIA_NOTEBOOK_PATH.read_text())[
            "metadata"
        ]["kernelspec"]
        dwave_metadata = json.loads(DWAVE_JULIA_NOTEBOOK_PATH.read_text())[
            "metadata"
        ]["kernelspec"]
        source = notebook_source(DWAVE_JULIA_NOTEBOOK_PATH)

        self.assertEqual(mathprog_metadata, dwave_metadata)
        self.assertEqual(1, source.count("using JuMP"))
        self.assertEqual(1, source.count("using QUBO"))
        self.assertEqual(1, source.count("using DWave"))


class NotebookPedagogyCellTests(unittest.TestCase):
    def test_each_notebook_has_three_exercise_checkpoints(self) -> None:
        for path in notebook_paths():
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cells(path)
                exercise_cells = [
                    cell
                    for cell in cells
                    if cell.get("cell_type") == "code"
                    and "# EXERCISE" in "".join(cell.get("source", []))
                ]
                solution_cells = [
                    cell
                    for cell in cells
                    if cell.get("cell_type") == "code"
                    and "# SOLUTION (hidden in workshop version):"
                    in "".join(cell.get("source", []))
                ]

                self.assertGreaterEqual(len(exercise_cells), 3)
                self.assertGreaterEqual(len(solution_cells), 3)
                self.assertTrue(
                    all(
                        {"hide-cell", "solution"}.issubset(
                            set(cell.get("metadata", {}).get("tags", []))
                        )
                        for cell in solution_cells[:3]
                    )
                )
                self.assertTrue(
                    all(
                        any(
                            stripped
                            and not stripped.startswith("#")
                            for stripped in (
                                line.strip()
                                for line in "".join(cell.get("source", [])).splitlines()
                            )
                        )
                        for cell in solution_cells
                    )
                )

    def test_setup_learning_objectives_and_prerequisites_are_top_cells(self) -> None:
        for path in notebook_paths():
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cells(path)

                if path.parent.name == "notebooks_jl":
                    pkg_indices = [
                        index
                        for index, cell in enumerate(cells)
                        if cell.get("cell_type") == "code"
                        and "Pkg.instantiate" in "".join(cell.get("source", []))
                    ]
                    self.assertEqual(1, len(pkg_indices))
                    self.assertEqual("import Pkg", notebook_first_heading(cells[pkg_indices[0]]))
                    learning_index = pkg_indices[0] + 1
                    prerequisites_index = pkg_indices[0] + 2
                else:
                    learning_index = 2
                    prerequisites_index = 3

                self.assertEqual("## Setup", notebook_first_heading(cells[1]))
                self.assertIn(
                    "Local installation",
                    "".join(cells[1].get("source", [])),
                )
                self.assertEqual(
                    "## Learning objectives",
                    notebook_first_heading(cells[learning_index]),
                )
                self.assertEqual(
                    "## Prerequisites",
                    notebook_first_heading(cells[prerequisites_index]),
                )
                self.assertIn(
                    "By the end of this notebook you will be able to:",
                    "".join(cells[learning_index].get("source", [])),
                )
                self.assertIn(
                    "**Prior notebooks:**",
                    "".join(cells[prerequisites_index].get("source", [])),
                )

    def test_summaries_close_learning_content(self) -> None:
        for path in notebook_paths():
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cells(path)
                summary_indices = [
                    index
                    for index, cell in enumerate(cells)
                    if notebook_first_heading(cell) in {"## Summary", "## Conclusion"}
                ]
                reference_indices = [
                    index
                    for index, cell in enumerate(cells)
                    if NOTEBOOK_REFERENCE_HEADING.match(notebook_first_heading(cell))
                ]

                self.assertEqual(1, len(summary_indices))
                summary_index = summary_indices[0]
                summary_source = "".join(cells[summary_index].get("source", []))

                self.assertIn("**Learning objectives met:**", summary_source)
                self.assertIn("**Next steps:**", summary_source)
                self.assertIn("**Further reading:**", summary_source)
                further_reading = summary_source.split("**Further reading:**", 1)[1]
                further_reading_items = [
                    line for line in further_reading.splitlines() if line.startswith("- ")
                ]
                self.assertGreaterEqual(len(further_reading_items), 2)

                if reference_indices:
                    self.assertEqual(reference_indices[0] - 1, summary_index)
                else:
                    self.assertEqual(len(cells) - 1, summary_index)


class NotebookPythonJuliaParityTests(unittest.TestCase):
    def test_practice_checkpoint_outputs_match_language_pairs(self) -> None:
        paired_notebooks = (
            (MATHPROG_JULIA_NOTEBOOK_PATH, MATHPROG_NOTEBOOK_PATH),
            (QUBO_JULIA_NOTEBOOK_PATH, QUBO_NOTEBOOK_PATH),
            (GAMA_JULIA_NOTEBOOK_PATH, GAMA_NOTEBOOK_PATH),
            (DWAVE_JULIA_NOTEBOOK_PATH, DWAVE_PYTHON_NOTEBOOK_PATH),
            (BENCHMARKING_JULIA_NOTEBOOK_PATH, BENCHMARKING_PYTHON_NOTEBOOK_PATH),
        )

        for julia_path, python_path in paired_notebooks:
            with self.subTest(
                julia=julia_path.relative_to(REPO_ROOT).as_posix(),
                python=python_path.relative_to(REPO_ROOT).as_posix(),
            ):
                julia_outputs = notebook_solution_output_texts(julia_path)
                python_outputs = notebook_solution_output_texts(python_path)

                self.assertEqual(3, len(julia_outputs))
                self.assertEqual(3, len(python_outputs))
                self.assertTrue(all(output.strip() for output in julia_outputs))
                self.assertTrue(all(output.strip() for output in python_outputs))
                self.assertEqual(julia_outputs, python_outputs)


class PythonPlotSamplesNotebookTests(unittest.TestCase):
    def assert_plot_samples_uses_initialized_energies(self, path: Path) -> None:
        cell_source = notebook_cell_source(path, "def plot_samples")
        function_source = notebook_function_source(path, "plot_samples")

        self.assertNotIn("results.vartype == 'Vartype.BINARY'", cell_source)
        self.assertIn("results.vartype == dimod.BINARY", cell_source)
        self.assertIn(
            "energies = [datum.energy for datum in results.data(",
            function_source,
        )
        self.assertLess(
            function_source.index("energies = [datum.energy"),
            function_source.index("if results.vartype"),
        )

    def test_qubo_python_plot_samples_uses_initialized_energies(self) -> None:
        self.assert_plot_samples_uses_initialized_energies(QUBO_NOTEBOOK_PATH)

    def test_benchmarking_python_plot_samples_uses_initialized_energies(self) -> None:
        self.assert_plot_samples_uses_initialized_energies(
            BENCHMARKING_PYTHON_NOTEBOOK_PATH
        )


class QUBOPythonGraphColoringTests(unittest.TestCase):
    def test_graph_coloring_uses_manual_dimod_bqm(self) -> None:
        source = notebook_source(QUBO_NOTEBOOK_PATH)
        bqm_source = notebook_cell_source(
            QUBO_NOTEBOOK_PATH,
            "def build_graph_coloring_bqm",
        )

        self.assertNotIn("dwavebinarycsp", source)
        self.assertIn("dimod.BinaryQuadraticModel", bqm_source)
        self.assertIn("bqm.offset += exactly_one_penalty", bqm_source)
        self.assertIn("bqm.add_linear(variable, -exactly_one_penalty)", bqm_source)
        self.assertIn("2 * exactly_one_penalty", bqm_source)
        self.assertIn("edge_penalty", bqm_source)

    def test_graph_coloring_validates_samples_without_csp_package(self) -> None:
        validator_source = notebook_cell_source(
            QUBO_NOTEBOOK_PATH,
            "def is_valid_coloring",
        )
        sampling_source = notebook_cell_source(QUBO_NOTEBOOK_PATH, "sample = None")

        self.assertIn("len(selected) != 1", validator_source)
        self.assertIn(
            "sample[color_var(v, color)] and sample[color_var(u, color)]",
            validator_source,
        )
        self.assertIn("is_valid_coloring(datum.sample)", sampling_source)
        self.assertNotIn("csp.check", sampling_source)


class BenchmarkingNotebookArchiveTests(unittest.TestCase):
    def test_python_results_zip_uses_local_cache_path(self) -> None:
        source = notebook_cell_source(BENCHMARKING_PYTHON_NOTEBOOK_PATH, "bundled_zip")

        self.assertIn("pickle_path = current_path / 'results'", source)
        self.assertIn("zip_name = pickle_path / 'results.zip'", source)
        self.assertIn("bundled_zip = current_path / 'results.zip'", source)
        self.assertIn("shutil.copyfile(bundled_zip, zip_name)", source)
        self.assertIn("urlretrieve(", source)
        self.assertNotIn("/content/results/results.zip", source)

    def test_python_results_zip_warns_before_expensive_regeneration(self) -> None:
        source = notebook_cell_source(
            BENCHMARKING_PYTHON_NOTEBOOK_PATH,
            "precomputed benchmark cache",
        )

        self.assertIn("approximately 3 hours of local computation", source)
        self.assertIn("Run the next cell to download", source)

    def test_raw_results_zip_is_extracted_with_zipfile(self) -> None:
        source = notebook_cell_source(BENCHMARKING_JULIA_NOTEBOOK_PATH, "use_raw_data")

        self.assertIn('bundled_zip = joinpath(@__DIR__, "results.zip")', source)
        self.assertIn("cp(bundled_zip, zip_name; force = true)", source)
        self.assertIn("extract_results_archive = isfile(zip_name)", source)
        self.assertIn("if extract_results_archive", source)
        self.assertIn("ZipFile.Reader(zip_name)", source)
        self.assertIn("for f in zr.files", source)
        self.assertIn("relpath(file_path, destination)", source)
        self.assertIn("Refusing to extract", source)
        self.assertIn("write(file_path, read(f))", source)
        self.assertNotIn("if isfile(zip_name) && use_raw_data", source)
        self.assertNotIn("gzip", source)
        self.assertNotIn("run(`", source)

    def test_results_archive_is_written_with_zipfile(self) -> None:
        source = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "# zip the processed benchmark summaries",
        )

        self.assertIn('joinpath(pickle_path, "results.zip")', source)
        self.assertIn("processed_result_file_names", source)
        self.assertIn('file_name == "all_results.json"', source)
        self.assertIn('startswith(file_name, "results_")', source)
        self.assertIn('endswith(file_name, ".json")', source)
        self.assertIn("ZipFile.Writer(zip_name)", source)
        self.assertIn("ZipFile.addfile(w, file_name)", source)
        self.assertIn("write(f, read(file_path))", source)
        self.assertNotIn("solutions_", source)
        self.assertNotIn("zip(pickle_path", source)

    def test_committed_results_archives_use_shared_json_cache(self) -> None:
        expected_names = ["all_results.json", "results_42.json"]

        for archive_path in BENCHMARKING_RESULTS_ARCHIVES:
            with self.subTest(archive=archive_path.relative_to(REPO_ROOT).as_posix()):
                self.assertTrue(archive_path.is_file())

                with zipfile.ZipFile(archive_path) as archive:
                    self.assertEqual(expected_names, sorted(archive.namelist()))
                    all_results = json.loads(archive.read("all_results.json"))
                    single_results = json.loads(archive.read("results_42.json"))

                self.assertIn("tts", single_results)
                self.assertIn("ttsci", single_results)
                self.assertNotIn("ttt", single_results)
                self.assertNotIn("tttci", single_results)

                first_instance = all_results[sorted(all_results, key=int)[0]]
                self.assertIn("tts", first_instance)
                self.assertIn("ttsci", first_instance)
                self.assertNotIn("ttt", first_instance)
                self.assertNotIn("tttci", first_instance)

    def test_python_processed_results_cache_uses_shared_json_schema(self) -> None:
        source = notebook_source(BENCHMARKING_PYTHON_NOTEBOOK_PATH)

        self.assertIn("import json", source)
        self.assertIn("def benchmark_cache_to_json(value):", source)
        self.assertIn("def benchmark_cache_from_json(value):", source)
        self.assertIn("return 'Infinity' if value > 0 else '-Infinity'", source)
        self.assertIn("return np.inf", source)
        self.assertIn("def normalize_single_results_cache(results):", source)
        self.assertIn("results['tts'] = results.pop('ttt')", source)
        self.assertIn("def boot_schedule_to_schedule_boot(boot_schedule):", source)
        self.assertIn(
            "def load_benchmark_cache(path, layout, default_sweep_count=None):",
            source,
        )
        self.assertIn(
            "raise ValueError('default_sweep_count is required for all-results caches')",
            source,
        )
        self.assertIn(
            "json.dump(benchmark_cache_to_json(data), file, allow_nan=False)",
            source,
        )
        self.assertIn(
            'results_json_name = "results_" + str(instance) + ".json"',
            source,
        )
        self.assertIn(
            "loaded_results = load_benchmark_cache(results_json_name, layout='single')",
            source,
        )
        self.assertIn("save_benchmark_cache(results_json_name, loaded_results)", source)
        self.assertIn(
            'all_results_json_name = os.path.join(pickle_path, "all_results.json")',
            source,
        )
        self.assertIn(
            "loaded_all_results = load_benchmark_cache(all_results_json_name, layout='all', default_sweep_count=default_sweeps)",
            source,
        )
        self.assertIn(
            "loaded_all_results = normalize_all_results_cache(pickle.load(open(all_results_name, \"rb\")), default_sweeps)",
            source,
        )
        self.assertIn("all_results[instance]['t'][schedule] = times", source)
        self.assertIn(
            "all_results[instance]['min_energy'][schedule] = min_energy",
            source,
        )
        self.assertIn(
            "all_results[instance]['random_energy'][schedule] = random_energy",
            source,
        )
        self.assertIn(
            "min_energy = all_results[instance]['min_energy'][schedule]",
            source,
        )
        self.assertIn(
            "random_energy = all_results[instance]['random_energy'][schedule]",
            source,
        )
        self.assertNotIn("['min_energy'][schedule][default_sweeps]", source)
        self.assertNotIn("['random_energy'][schedule][default_sweeps]", source)
        self.assertIn("save_benchmark_cache(all_results_json_name, all_results)", source)

    def test_julia_processed_results_cache_uses_python_compatible_json_schema(
        self,
    ) -> None:
        source = notebook_source(BENCHMARKING_JULIA_NOTEBOOK_PATH)

        self.assertIn("function benchmark_cache_to_json(value)", source)
        self.assertIn("return \"Infinity\"", source)
        self.assertIn("return Inf", source)
        self.assertIn("function export_summary_results(raw)", source)
        self.assertIn('"tts"           => benchmark_cache_to_json(raw[:ttt])', source)
        self.assertIn('"ttsci"         => benchmark_cache_to_json(raw[:tttci])', source)
        self.assertIn("JSON.print(io, export_summary_results(results))", source)
        self.assertIn('key_aliases = Dict("tts" => "ttt", "ttsci" => "tttci")', source)
        self.assertIn("function export_all_results(raw)", source)
        self.assertIn('"tts"           => export_schedule_boot_dict(raw[:ttt])', source)
        self.assertIn('"ttsci"         => export_schedule_boot_dict(raw[:tttci])', source)
        self.assertIn(
            ':ttt => restore_metric_dict(metric_raw(raw, "ttt", "tts"), default_sweep_count)',
            source,
        )
        self.assertIn(
            ':tttci => restore_metric_dict(metric_raw(raw, "tttci", "ttsci"), default_sweep_count)',
            source,
        )
        self.assertIn(
            "restore_all_results(JSON.parsefile(all_results_name), default_sweeps)",
            source,
        )
        self.assertIn("JSON.print(io, export_all_results(all_results))", source)

    def test_julia_solution_cache_uses_current_bqpjson_format(self) -> None:
        source = notebook_source(BENCHMARKING_JULIA_NOTEBOOK_PATH)

        self.assertIn("QUBOTools.Format{:bqpjson}", source)
        self.assertIn("fmt[:version]", source)
        self.assertNotIn("QUBOTools.BQPJSON", source)
        self.assertNotIn("fmt.version", source)

    def test_julia_solution_cache_reuses_json_solution_files(self) -> None:
        source = notebook_source(BENCHMARKING_JULIA_NOTEBOOK_PATH)

        self.assertIn(
            '"solutions_$(total_reads)_$(sweep)_$(schedule).json"',
            source,
        )
        self.assertIn("if isfile(solution_name) && !overwrite_pickles", source)
        self.assertIn("if isfile(sol_filename) && !overwrite_pickles", source)
        self.assertIn("QUBOTools.read_solution(solution_name)", source)
        self.assertIn("QUBOTools.read_solution(sol_filename)", source)
        self.assertNotIn('"$(instance)_$(schedule)_$(sweep).p"', source)

    def test_julia_solution_cache_documents_filename_schemes(self) -> None:
        source = notebook_source(BENCHMARKING_JULIA_NOTEBOOK_PATH)

        self.assertIn("Single-instance cache: the key includes total_reads", source)
        self.assertIn("Reuse the single-instance cache from the sweep study above", source)
        self.assertIn("Per-instance cache: the key includes instance", source)
        self.assertIn("Per-instance sweep cache for ensemble timing", source)
        self.assertIn("Benchmark-instance cache: this key includes instance", source)
        self.assertIn("Per-instance approx-ratio cache", source)

    def test_julia_solution_cache_round_trips_sampleset_metadata(self) -> None:
        reader = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "function QUBOTools.read_solution",
        )
        writer = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "function QUBOTools.write_solution",
        )

        self.assertIn("QUBOTools.Sample{Float64, Int}[]", reader)
        self.assertIn("QUBOTools.SampleSet{Float64, Int}", reader)
        self.assertIn("metadata = metadata", reader)
        self.assertIn("domain = :spin", reader)
        self.assertIn("metadata = QUBOTools.metadata(sol)", writer)
        self.assertIn('"metadata"        => metadata', writer)
        self.assertNotIn("Fallback", reader + writer)
        self.assertNotIn("cite_start", reader + writer)
        self.assertNotIn("Try using", reader + writer)

    def test_julia_multi_instance_results_cache_restores_key_types(self) -> None:
        source = notebook_cell_source(BENCHMARKING_JULIA_NOTEBOOK_PATH, "restore_all_results")

        self.assertIn("if isfile(all_results_name) && !use_raw_data", source)
        self.assertIn(
            "restore_all_results(JSON.parsefile(all_results_name), default_sweeps)",
            source,
        )
        self.assertIn(
            "parse(Int, string(k)) => restore_instance_results(v, default_sweep_count)",
            source,
        )
        self.assertIn("function has_numeric_keys(raw)", source)
        self.assertIn(
            "function unwrap_default_sweep(raw, default_sweep_count)",
            source,
        )
        self.assertIn("string(default_sweep_count)", source)
        self.assertIn(
            "function restore_schedule_boot_dict(raw, default_sweep_count)",
            source,
        )
        self.assertIn(
            ":ttt => restore_metric_dict(metric_raw(raw, \"ttt\", \"tts\"), default_sweep_count)",
            source,
        )
        self.assertIn(
            ":tttci => restore_metric_dict(metric_raw(raw, \"tttci\", \"ttsci\"), default_sweep_count)",
            source,
        )
        self.assertIn(
            ":min_energy => restore_schedule_dict(raw[\"min_energy\"], default_sweep_count)",
            source,
        )

    def test_julia_cached_single_instance_plots_use_available_schedule(self) -> None:
        performance_plot = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "title_str = \"Simulated annealing Performance Ratio of Ising $(benchmark_instance)",
        )
        runtime_plot = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "title_str = \"Simulated annealing expected total runtime",
        )
        adapted_runtime_plot = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "function plot_ttt_grid_adapted",
        )

        for source in (performance_plot, runtime_plot, adapted_runtime_plot):
            self.assertIn("schedules_to_plot = [primary_schedule]", source)

        self.assertIn("for schedule in schedules_to_plot", performance_plot)
        self.assertIn("for schedule in schedules_to_plot", runtime_plot)
        self.assertIn("schedules_to_plot,", adapted_runtime_plot)
        self.assertNotIn("    schedules, \n    results;", adapted_runtime_plot)

    def test_julia_results_zip_skips_zip32_overflow(self) -> None:
        source = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "archive_size_limit = typemax(UInt32)",
        )

        self.assertIn("archive_size_bytes > archive_size_limit", source)
        self.assertIn("Skipping results.zip archive", source)
        self.assertIn("processed result set", source)
        self.assertIn("ZIP64", source)


class BenchmarkingNotebookScopeTests(unittest.TestCase):
    def test_python_min_sweep_is_defined_before_first_use(self) -> None:
        source = notebook_source(BENCHMARKING_PYTHON_NOTEBOOK_PATH)

        definition = "min_sweep = sweeps[int(np.nanargmin(tts_for_min_sweep))]"
        first_use = "num=min_sweep"

        self.assertIn(definition, source)
        self.assertLess(source.index(definition), source.index(first_use))

    def test_julia_min_median_index_is_computed_without_global_scope_escape(self) -> None:
        source = notebook_source(BENCHMARKING_JULIA_NOTEBOOK_PATH)

        helper_definition = (
            "function min_median_ttt(all_results, instances, boot, schedule)"
        )
        summary_lookup = "primary_median_summary = median_summary_by_schedule[primary_schedule]"
        definition = "min_median_index = primary_median_summary.min_median_index"
        later_use = "min_median_sweep = sweeps[min_median_index]"

        self.assertIn(helper_definition, source)
        self.assertIn(summary_lookup, source)
        self.assertIn(definition, source)
        self.assertNotIn("global min_median_index", source)
        self.assertNotIn("min_median_index = 1", source)
        self.assertLess(source.index(helper_definition), source.index(summary_lookup))
        self.assertLess(source.index(summary_lookup), source.index(definition))
        self.assertLess(source.index(definition), source.index(later_use, source.index(definition)))

    def test_julia_ising_model_spin_variable_does_not_shadow_success_probability(
        self,
    ) -> None:
        source = notebook_source(BENCHMARKING_JULIA_NOTEBOOK_PATH)
        model_cell = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "ising_model = Model()",
        )
        solve_cell = notebook_cell_source(
            BENCHMARKING_JULIA_NOTEBOOK_PATH,
            "set_optimizer(ising_model, DWave.Neal.Optimizer)",
        )

        self.assertIn("@variable(ising_model, s_var[1:11], Spin)", model_cell)
        self.assertIn(
            "@objective(ising_model, Min, s_var' * J * s_var + h' * s_var + β)",
            model_cell,
        )
        self.assertIn("ising_s = round.(Int, value.(s_var))", solve_cell)
        self.assertNotIn("@variable(ising_model, s[1:11], Spin)", source)
        self.assertNotIn("value.(s))", solve_cell)

    def test_julia_benchmarking_expensive_outputs_are_not_committed(self) -> None:
        notebook = json.loads(BENCHMARKING_JULIA_NOTEBOOK_PATH.read_text())
        results_cells = [
            (index, cell)
            for index, cell in enumerate(notebook["cells"])
            if cell.get("cell_type") == "code"
            and "success_probability = 0.99" in "".join(cell.get("source", []))
            and "results = Dict{Symbol,Any}" in "".join(cell.get("source", []))
        ]
        plot_cells = [
            index
            for index, cell in enumerate(notebook["cells"])
            if cell.get("cell_type") == "code"
            and "function plot_progress" in "".join(cell.get("source", []))
        ]

        self.assertEqual(1, len(results_cells))
        self.assertEqual(1, len(plot_cells))

        results_index, results_cell = results_cells[0]
        self.assertLess(results_index, plot_cells[0])
        self.assertFalse(results_cell.get("outputs"))

        expensive_cells = [
            cell
            for cell in notebook["cells"][plot_cells[0] :]
            if cell.get("cell_type") == "code"
            and any(
                marker in "".join(cell.get("source", []))
                for marker in (
                    "function plot_progress",
                    "title_str =",
                    "Calculating optimal sweep",
                    "plt = plot(",
                    "plt_approx = plot(",
                    "plt_total_reads = plot(",
                )
            )
        ]

        self.assertTrue(expensive_cells)
        self.assertTrue(
            all(not cell.get("outputs") for cell in expensive_cells)
        )


class QUBOJuliaNotebookTests(unittest.TestCase):
    def test_graph_coloring_constraint_container_is_not_displayed(self) -> None:
        source = notebook_cell_source(
            QUBO_JULIA_NOTEBOOK_PATH,
            "@constraint(color_model, neigh",
        )

        self.assertIn(
            "@constraint(color_model, neigh[(i,j) ∈ E, k=1:3], c[i, k] * c[j,k] == 0);",
            source,
        )
        self.assertNotIn("InvalidConstraintRef", notebook_output_text(QUBO_JULIA_NOTEBOOK_PATH))

    def test_ising_ilp_objective_keeps_linear_and_quadratic_terms_separate(self) -> None:
        source = notebook_cell_source(QUBO_JULIA_NOTEBOOK_PATH, "ising_ilp_model = Model()")

        self.assertIn(
            '@variable(ising_ilp_model, x_ising_ilp[1:n], Bin, base_name = "x")',
            source,
        )
        self.assertIn("@variable(ising_ilp_model, y[1:n, 1:n], Bin)", source)
        self.assertIn("sum(L[i] * x_ising_ilp[i] for i in 1:n)", source)
        self.assertIn("sum(Q[i,j] * y[i,j] for i in 1:n, j in 1:n if i != j)", source)
        self.assertNotIn("i == j ? x[i] : y[i,j]", source)

    def test_ising_ilp_solution_is_checked_against_exact_sampler(self) -> None:
        source = notebook_cell_source(QUBO_JULIA_NOTEBOOK_PATH, "ising_ilp_x = round")

        self.assertIn("ising_ilp_s = 2 .* ising_ilp_x .- 1", source)
        self.assertIn("@assert ising_ilp_s == ising_s", source)
        self.assertIn(
            "@assert isapprox(objective_value(ising_ilp_model), objective_value(ising_model); atol = 1e-6)",
            source,
        )

    def test_ising_ilp_markdown_documents_substitution_and_correct_result(self) -> None:
        substitution = notebook_cell_source(
            QUBO_JULIA_NOTEBOOK_PATH,
            "Before rebuilding the Ising model as a binary ILP",
        )
        result = notebook_cell_source(QUBO_JULIA_NOTEBOOK_PATH, "The corrected ILP solution")

        self.assertIn("$s = 2x - 1$", substitution)
        self.assertIn("linear vector $L$", substitution)
        self.assertIn("strictly off-diagonal quadratic matrix $Q$", substitution)
        self.assertIn("$x = [0,0,0,0,0,0,0,0,1,0,0]$", result)
        self.assertIn("$s = [-1,-1,-1,-1,-1,-1,-1,-1,+1,-1,-1]$", result)
        self.assertIn("objective value $5.0$", result)


class ParseExecutionTimeoutSecondsTests(unittest.TestCase):
    def test_uses_default_timeout_when_env_is_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(verify_notebooks.parse_execution_timeout_seconds(), 1200)

    def test_accepts_valid_integer_timeout(self) -> None:
        with patch.dict(
            os.environ,
            {"QUBONOTEBOOKS_NOTEBOOK_TIMEOUT": "3600"},
            clear=True,
        ):
            self.assertEqual(verify_notebooks.parse_execution_timeout_seconds(), 3600)

    def test_rejects_non_integer_timeout_with_clear_message(self) -> None:
        with patch.dict(
            os.environ,
            {"QUBONOTEBOOKS_NOTEBOOK_TIMEOUT": "fast"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"Invalid QUBONOTEBOOKS_NOTEBOOK_TIMEOUT value 'fast': must be an integer number of seconds\.",
            ):
                verify_notebooks.parse_execution_timeout_seconds()

    def test_rejects_non_positive_timeout_with_clear_message(self) -> None:
        with patch.dict(
            os.environ,
            {"QUBONOTEBOOKS_NOTEBOOK_TIMEOUT": "0"},
            clear=True,
        ):
            with self.assertRaisesRegex(
                ValueError,
                r"Invalid QUBONOTEBOOKS_NOTEBOOK_TIMEOUT value '0': must be a positive integer number of seconds\.",
            ):
                verify_notebooks.parse_execution_timeout_seconds()


class JuliaExecutableTests(unittest.TestCase):
    def test_defaults_to_julia(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(verify_notebooks.find_julia_executable(), "julia")

    def test_prefers_julia_bin(self) -> None:
        with patch.dict(os.environ, {"JULIA": "/tmp/julia-a", "JULIA_BIN": "/tmp/julia-b"}):
            self.assertEqual(verify_notebooks.find_julia_executable(), "/tmp/julia-b")


class NotebookClassificationTests(unittest.TestCase):
    def test_default_notebooks_are_portable_today(self) -> None:
        self.assertEqual(
            verify_notebooks.DEFAULT_NOTEBOOKS,
            (
                Path("notebooks_py/2-QUBO_python.ipynb"),
                Path("notebooks_py/3-GAMA_python.ipynb"),
            ),
        )

    def test_classifies_supported_notebook_paths(self) -> None:
        self.assertEqual(
            verify_notebooks.classify_notebook(Path("notebooks_py/1-MathProg_python.ipynb")),
            "python",
        )
        self.assertEqual(
            verify_notebooks.classify_notebook(Path("notebooks_jl/1-MathProg.ipynb")),
            "julia",
        )

    def test_rejects_unsupported_notebook_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported notebook path"):
            verify_notebooks.classify_notebook(Path("templates/qubo.ipynb"))


class KernelSpecTests(unittest.TestCase):
    def test_python_kernel_spec_is_written_under_jupyter_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            kernel_name, env = verify_notebooks.python_kernel_spec_dir(tmp)
            kernel_path = tmp / "kernels" / kernel_name / "kernel.json"
            kernel = json.loads(kernel_path.read_text())

        self.assertEqual(kernel_name, "qubonotebooks-python-local")
        self.assertEqual(env["JUPYTER_PATH"], str(tmp))
        self.assertIn("ipykernel_launcher", kernel["argv"])
        self.assertEqual(kernel["display_name"], "QUBONotebooks Python (local)")

    def test_julia_kernel_spec_uses_shared_notebooks_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            kernel_name, env = verify_notebooks.julia_kernel_spec_dir(
                tmp,
                julia_executable="/tmp/julia",
            )
            kernel_path = tmp / "kernels" / kernel_name / "kernel.json"
            kernel = json.loads(kernel_path.read_text())

        self.assertEqual(kernel_name, "qubonotebooks-julia-local")
        self.assertEqual(env["JUPYTER_PATH"], str(tmp))
        self.assertEqual(kernel["argv"][0], "/tmp/julia")
        self.assertIn(f"--project={REPO_ROOT / 'notebooks_jl'}", kernel["argv"])
        self.assertEqual(kernel["display_name"], "QUBONotebooks Julia (local)")


class CommandConstructionTests(unittest.TestCase):
    @patch.object(verify_notebooks, "run")
    def test_instantiates_current_shared_julia_project(
        self,
        run_mock: Mock,
    ) -> None:
        with patch.dict(os.environ, {}, clear=True):
            verify_notebooks.instantiate_julia_project("/tmp/julia")

        cmd = run_mock.call_args.args[0]
        env = run_mock.call_args.kwargs["env"]

        self.assertEqual(cmd[:2], ["/tmp/julia", "--project=./notebooks_jl"])
        self.assertIn("Pkg.instantiate()", cmd[3])
        self.assertIn(str(REPO_ROOT / ".julia-depot"), env["JULIA_DEPOT_PATH"])
        self.assertEqual(env["JULIA_PKG_PRECOMPILE_AUTO"], "0")

    @patch.object(verify_notebooks, "run")
    def test_execute_notebook_uses_jupyter_nbconvert(
        self,
        run_mock: Mock,
    ) -> None:
        verify_notebooks.execute_notebook(
            Path("notebooks_py/1-MathProg_python.ipynb"),
            timeout_seconds=42,
            kernel_name="test-kernel",
            env={"JUPYTER_PATH": "/tmp/kernels"},
        )

        cmd = run_mock.call_args.args[0]
        env = run_mock.call_args.kwargs["env"]

        self.assertIn("nbconvert", cmd)
        self.assertIn("--execute", cmd)
        self.assertIn("--ExecutePreprocessor.timeout=42", cmd)
        self.assertIn("--ExecutePreprocessor.kernel_name=test-kernel", cmd)
        self.assertEqual(cmd[-1], "notebooks_py/1-MathProg_python.ipynb")
        self.assertEqual(env, {"JUPYTER_PATH": "/tmp/kernels"})


class RepositoryCommandTests(unittest.TestCase):
    def test_makefile_exposes_verification_targets(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text()

        self.assertIn("test-python:", makefile)
        self.assertIn("test-julia:", makefile)
        self.assertIn("check-notebook-output-hygiene:", makefile)
        self.assertIn("clear-notebook-outputs:", makefile)
        self.assertIn("verify-notebooks:", makefile)
        self.assertIn("verify-python-portable:", makefile)
        self.assertIn("verify-qubo-python:", makefile)
        self.assertIn("verify-gama-python:", makefile)
        self.assertIn("verify-benchmarking-python:", makefile)
        self.assertIn("verify-qaoa-julia-local:", makefile)
        self.assertIn("PORTABLE_PYTHON_NOTEBOOKS", makefile)
        self.assertIn("ClearOutputPreprocessor.enabled=True", makefile)
        self.assertIn("git grep -lE", makefile)
        self.assertNotIn("git grep -nE 'C:", makefile)
        self.assertIn("purdue-internship", makefile)
        self.assertIn("QUBONotebooksFork", makefile)
        self.assertIn("./scripts/verify_notebooks.py", makefile)
        self.assertIn("--project=./notebooks_jl", makefile)
        self.assertIn("$(UV) sync --locked", makefile)
        self.assertIn("$(UV) run --locked", makefile)

    def test_ci_runs_notebook_output_hygiene_check(self) -> None:
        ci_workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()

        self.assertIn("Notebook output hygiene", ci_workflow)
        self.assertIn("make check-notebook-output-hygiene", ci_workflow)

    def test_locked_python_environment_excludes_unpatched_diskcache_path(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        lock = (REPO_ROOT / "uv.lock").read_text()

        self.assertNotIn("dwave-ocean-sdk", pyproject)
        self.assertNotIn("dwave-ocean-sdk", lock)
        self.assertNotIn("dwavebinarycsp", pyproject)
        self.assertNotIn("dwavebinarycsp", lock)
        self.assertNotIn('name = "diskcache"', lock)
        self.assertIn("GHSA-w8v5-vhqr-4h9v", (REPO_ROOT / "README.md").read_text())

    def test_qubo_dependency_group_includes_notebook_runtime_packages(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        qubo_group = pyproject[
            pyproject.index("qubo = [") : pyproject.index("\n]\n\n[tool.uv]")
        ]

        self.assertIn('"dimod', qubo_group)
        self.assertIn('"dwave-neal', qubo_group)

    def test_sysimage_scripts_use_current_julia_notebook_project(self) -> None:
        create_sysimage = (REPO_ROOT / "scripts" / "create_sysimage.jl").read_text()
        prepare_release = (REPO_ROOT / "scripts" / "prepare_release.jl").read_text()

        self.assertIn('"notebooks_jl"', create_sysimage)
        self.assertIn('"notebooks_jl"', prepare_release)
        self.assertNotIn('"notebooks"', create_sysimage)
        self.assertNotIn('"notebooks"', prepare_release)

    def test_colab_installer_default_matches_sysimage_julia_version(self) -> None:
        install_script = (REPO_ROOT / "scripts" / "install-colab-julia.sh").read_text()
        deploy_workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text()
        notebook_manifest = (REPO_ROOT / "notebooks_jl" / "Manifest.toml").read_text()
        expected_version = "1.10.11"

        self.assertIn(f'install-colab-julia "{expected_version}" 2', install_script)
        self.assertIn(f"julia-version: '{expected_version}'", deploy_workflow)
        self.assertIn(f'julia_version = "{expected_version}"', notebook_manifest)

    def test_sysimage_build_and_colab_kernel_use_matching_depot_path(self) -> None:
        install_script = (REPO_ROOT / "scripts" / "install-colab-julia.sh").read_text()
        deploy_workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text()
        release_notes = (REPO_ROOT / ".github" / "workflows" / "NOTES.md").read_text()

        self.assertIn(
            "JULIA_DEPOT_PATH: /content/.julia-depot:/home/runner/.julia",
            deploy_workflow,
        )
        self.assertIn("sudo mkdir -p /content/.julia-depot", deploy_workflow)
        self.assertIn('COLAB_JULIA_DEPOT="/content/.julia-depot"', install_script)
        self.assertIn('export JULIA_DEPOT_PATH="$COLAB_JULIA_DEPOT:', install_script)
        self.assertIn('"JULIA_DEPOT_PATH"=>ENV["JULIA_DEPOT_PATH"]', install_script)
        self.assertIn("tar -xzf sysimage.tar.gz -C /content", release_notes)
        self.assertIn('export JULIA_DEPOT_PATH="/content/.julia-depot:', release_notes)

    def test_sysimage_includes_julia_qubo_and_gama_runtime_packages(self) -> None:
        create_sysimage = (REPO_ROOT / "scripts" / "create_sysimage.jl").read_text()
        package_lines = {line.strip() for line in create_sysimage.splitlines()}

        expected_packages = {
            '"BinaryWrappers",',
            '"DWave",',
            '"Graphs",',
            '"JuMP",',
            '"Karnak",',
            '"lib4ti2_jll",',
            '"Luxor",',
            '"Measures",',
            '"NPZ",',
            '"Plots",',
            '"PythonCall",',
            '"QiskitOpt",',
            '"QUBO",',
            '"StatsBase",',
            '"StatsPlots",',
        }

        self.assertTrue(
            expected_packages.issubset(package_lines),
            expected_packages - package_lines,
        )


class JuliaColabSetupTests(unittest.TestCase):
    def test_all_julia_notebooks_use_native_colab_julia_bootstrap(self) -> None:
        for path in JULIA_COLAB_NOTEBOOK_PATHS:
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cell_sources(path)
                setup_indexes = [
                    i
                    for i, source in enumerate(cells)
                    if (
                        "Base.invokelatest(QUBONotebooksBootstrap.bootstrap_notebook"
                        in source
                    )
                ]
                activate_indexes = [
                    i for i, source in enumerate(cells) if "Pkg.activate(JULIA_PROJECT_DIR)" in source
                ]
                expected_call = (
                    "Base.invokelatest("
                    f'QUBONotebooksBootstrap.bootstrap_notebook, "{path.stem}")'
                )
                metadata = json.loads(path.read_text())["metadata"]["kernelspec"]

                self.assertEqual(1, len(setup_indexes))
                self.assertIn(expected_call, cells[setup_indexes[0]])
                self.assertTrue(activate_indexes)
                self.assertLess(setup_indexes[0], min(activate_indexes))
                self.assertNotIn("%%shell", notebook_source(path))
                self.assertNotIn("install-colab-julia.sh", notebook_source(path))
                self.assertEqual(
                    {"display_name": "Julia", "language": "julia", "name": "julia"},
                    metadata,
                )

    def test_dwave_installation_badge_targets_existing_anchor(self) -> None:
        source = notebook_source(DWAVE_JULIA_NOTEBOOK_PATH)

        self.assertIn('href="#installation"', source)
        self.assertRegex(source, r'<a\b[^>]*(?:id|name)="installation"')

    def test_bootstrap_supports_native_colab_runtime_failure_modes(self) -> None:
        source = BOOTSTRAP_PATH.read_text()

        self.assertIn("module QUBONotebooksBootstrap", source)
        self.assertIn("COLAB_RELEASE_TAG", source)
        self.assertIn("git clone --depth 1 https://github.com/JuliaQUBO/QUBONotebooks.git", source)
        self.assertIn("QUBONOTEBOOKS_REPO_DIR", source)
        self.assertIn("Base.invokelatest", notebook_source(MATHPROG_JULIA_NOTEBOOK_PATH))
        self.assertIn("configured_allow_mismatch = env_bool(ALLOW_VERSION_MISMATCH_ENV)", source)
        self.assertIn("Colab will allow Pkg to re-resolve the notebook environment", source)
        self.assertIn("Resolving Julia packages for current runtime Julia", source)
        self.assertIn("Pkg.resolve()", source)
        self.assertIn("Pkg.update()", source)
        self.assertIn('ENV["JULIA_CONDAPKG_BACKEND"] = "Null"', source)
        self.assertIn('python_packages::Vector{String} = ["dwave-ocean-sdk"]', source)


class PythonNotebookDependencySetupTests(unittest.TestCase):
    def test_mathprog_pins_stable_idaes_and_guards_solver_use(self) -> None:
        source = notebook_source(MATHPROG_NOTEBOOK_PATH)
        install_cell = notebook_cell_source(MATHPROG_NOTEBOOK_PATH, "idaes-pse==2.12.0")
        ipopt_cell = notebook_cell_source(MATHPROG_NOTEBOOK_PATH, "configure IPOPT")
        bonmin_cell = notebook_cell_source(MATHPROG_NOTEBOOK_PATH, "# Define the solver BONMIN")
        couenne_cell = notebook_cell_source(MATHPROG_NOTEBOOK_PATH, "# Define the solver COUENNE")

        self.assertNotIn("idaes-pse --pre", source)
        self.assertNotIn(".available()", source)
        self.assertNotIn("Re-run the IDAES install cell", source)
        self.assertIn("!pip install idaes-pse==2.12.0", install_cell)
        self.assertIn("Install IDAES solver extensions", install_cell)
        self.assertIn("for solver_name in ['ipopt', 'bonmin', 'couenne']:", install_cell)
        self.assertIn("Check the install output above", install_cell)
        self.assertIn("solver.available(exception_flag=False)", install_cell)
        self.assertIn("opt_ipopt.available(exception_flag=False)", install_cell)
        self.assertIn("IDAES solver setup cell", ipopt_cell)
        self.assertIn("opt_bonmin.available(exception_flag=False)", bonmin_cell)
        self.assertIn("IDAES solver setup cell", bonmin_cell)
        self.assertIn("opt_couenne.available(exception_flag=False)", couenne_cell)
        self.assertIn("IDAES solver setup cell", couenne_cell)

    def test_qci_pins_stable_idaes_and_guards_solver_use(self) -> None:
        source = notebook_source(QCI_NOTEBOOK_PATH)
        install_cell = notebook_cell_source(QCI_NOTEBOOK_PATH, "idaes-pse==2.12.0")
        ipopt_cell = notebook_cell_source(QCI_NOTEBOOK_PATH, "Simple_Quadratic_Program")
        enumeration_cell = notebook_cell_source(QCI_NOTEBOOK_PATH, "simple_qubo_energy")
        cbc_cell = notebook_cell_source(QCI_NOTEBOOK_PATH, "Constrained_Linear_Integer_Program")

        self.assertNotIn("idaes-pse --pre", source)
        self.assertNotIn(".available()", source)
        self.assertNotIn("Re-run the IDAES install cell", source)
        self.assertIn("!pip install idaes-pse==2.12.0", install_cell)
        self.assertIn("Install IDAES solver extensions", install_cell)
        self.assertIn("for solver_name in ['ipopt', 'cbc']:", install_cell)
        self.assertNotIn("bonmin", install_cell.lower())
        self.assertIn("Check the install output above", install_cell)
        self.assertIn("solver.available(exception_flag=False)", install_cell)
        self.assertIn('api_token = os.environ.get("QCI_TOKEN", "")', source)
        self.assertIn('userdata.get("QCI_TOKEN")', source)
        self.assertIn("### QCI API token", source)
        self.assertIn("Set the QCI_TOKEN environment variable or Colab Secret", source)
        self.assertIn("The Dirac cloud examples require a QCI token", source)
        self.assertNotIn("QCI_API_TOKEN", source)
        self.assertNotIn('api_token = ""', source)
        self.assertIn("IPOPT not found", ipopt_cell)
        self.assertIn("IDAES solver setup cell", ipopt_cell)
        self.assertIn("itertools.product([0, 1], repeat=2)", enumeration_cell)
        self.assertNotIn("BONMIN not found", source)
        self.assertIn("CBC not found", cbc_cell)
        self.assertIn("IDAES solver setup cell", cbc_cell)

    def test_benchmarking_installs_progress_dependency(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        qubo_group = pyproject[
            pyproject.index("qubo = [") : pyproject.index("\n]\n\n[tool.uv]")
        ]
        local_setup_cell = notebook_cell_source(
            BENCHMARKING_PYTHON_NOTEBOOK_PATH,
            "python -m pip install dimod dwave-neal",
        )
        colab_install_cell = notebook_cell_source(
            BENCHMARKING_PYTHON_NOTEBOOK_PATH,
            "!pip install -q pyomo dimod",
        )

        self.assertIn("tqdm", local_setup_cell)
        self.assertIn("tqdm", colab_install_cell)
        self.assertIn('"tqdm', qubo_group)

    def test_qci_constrained_polynomial_model_solves_wrapped_model(self) -> None:
        source = notebook_source(QCI_NOTEBOOK_PATH)
        model_cell = notebook_cell_source(
            QCI_NOTEBOOK_PATH, "constraint_model = ScalarConstrainedPolynomialModel"
        )
        result_cell = notebook_cell_source(QCI_NOTEBOOK_PATH, "best_objective_value")

        self.assertIn("from eqc_models.base.operators import Polynomial", source)
        self.assertIn(
            "class ScalarConstrainedPolynomialModel(ConstrainedPolynomialModel)",
            source,
        )
        self.assertIn("return float(np.asarray(value).reshape(-1)[0])", source)
        self.assertIn(
            "ConstrainedPolynomialModel wraps the QUBO with explicit constraints",
            model_cell,
        )
        self.assertIn(
            "constraint_model = ScalarConstrainedPolynomialModel",
            model_cell,
        )
        self.assertIn("response = solver.solve(constraint_model", model_cell)
        self.assertNotIn("response = solver.solve(model", model_cell)
        self.assertIn(
            "constraint_model.offset * constraint_model.penalty_multiplier",
            result_cell,
        )

    def test_qubo_colab_install_includes_scipy_before_imports(self) -> None:
        cells = notebook_cell_sources(QUBO_NOTEBOOK_PATH)
        install_cell = notebook_cell_source(QUBO_NOTEBOOK_PATH, "!pip install -q pyomo")
        import_cell = notebook_cell_source(QUBO_NOTEBOOK_PATH, "import networkx as nx")

        self.assertIn("dimod", install_cell)
        self.assertIn("scipy", install_cell)
        self.assertIn("pandas", install_cell)
        self.assertIn("networkx", install_cell)
        self.assertLess(cells.index(install_cell), cells.index(import_cell))

    def test_gama_installs_missing_dimod_and_neal_outside_colab(self) -> None:
        install_cell = notebook_cell_source(GAMA_NOTEBOOK_PATH, "subprocess.check_call")

        self.assertIn("try:\n    import dimod\n    import neal", install_cell)
        self.assertIn(
            '[sys.executable, "-m", "pip", "install", "dimod", "dwave-neal"]',
            install_cell,
        )
        self.assertNotIn("if IN_COLAB", install_cell)


class GamaNotebookTests(unittest.TestCase):
    def test_gama_greedy_rejects_empty_candidate_sets(self) -> None:
        function_source = notebook_function_source(GAMA_NOTEBOOK_PATH, "greedy")
        namespace: dict[str, object] = {}

        exec(function_source, namespace)
        greedy = namespace["greedy"]

        with self.assertRaisesRegex(ValueError, "empty candidate set"):
            greedy([])

        self.assertEqual((1, (4.0, 2)), greedy([(5.0, 0), (4.0, 2), (3.0, 1)]))
        self.assertEqual((1, (4.0, 0)), greedy([(5.0, 0), (4.0, 0)]))

    def test_gama_greedy_short_circuits_on_first_improving_candidate(self) -> None:
        function_source = notebook_function_source(GAMA_NOTEBOOK_PATH, "greedy")
        namespace: dict[str, object] = {}

        exec(function_source, namespace)
        greedy = namespace["greedy"]

        def candidates():
            yield (5.0, 2)
            raise AssertionError("greedy() evaluated candidates after the first improvement")

        self.assertEqual((0, (5.0, 2)), greedy(candidates()))

    def test_gama_notebook_has_portable_py4ti2_fallback(self) -> None:
        source = notebook_source(GAMA_NOTEBOOK_PATH)

        self.assertIn("HAS_PY4TI2", source)
        self.assertIn("load_precomputed_graver_basis", source)
        self.assertIn("notebooks_py/graver.npy", source)
        self.assertIn("3-GAMA_example4_feasible_starts.csv", source)
        self.assertIn("np.random.default_rng(271828)", source)

        for path in GAMA_DATA_FILES:
            self.assertTrue(path.is_file(), f"{path} should be committed")

    def test_gama_notebook_outputs_are_refreshed(self) -> None:
        notebook = json.loads(GAMA_NOTEBOOK_PATH.read_text())
        code_cells = [
            cell for cell in notebook["cells"] if cell.get("cell_type") == "code"
        ]
        substantive_cells = [
            cell
            for cell in code_cells
            if not (
                (source := "".join(cell.get("source", []))).startswith(
                    ("try:", "from pathlib import Path")
                )
                or "# EXERCISE" in source
                or "# SOLUTION (hidden in workshop version):" in source
            )
        ]

        self.assertTrue(substantive_cells)
        self.assertTrue(
            all(cell.get("execution_count") is not None for cell in substantive_cells)
        )
        self.assertGreater(sum(bool(cell.get("outputs", [])) for cell in code_cells), 0)


class DWaveNotebookTests(unittest.TestCase):
    def test_julia_topology_section_uses_current_sampler_topology(self) -> None:
        source = notebook_source(DWAVE_JULIA_NOTEBOOK_PATH)

        self.assertIn('solver=Dict("qpu" => true)', source)
        self.assertIn('set_optimizer_attribute(qubo_model, "return_embedding", true)', source)
        self.assertIn("DWave.WorkingGraph(sampler)", source)
        self.assertIn("DWave.WorkingGraph(QUBOTools.metadata(sampleset))", source)
        self.assertIn("DWave.embedding(sampleset)", source)
        self.assertIn("DWave.draw_topology(arch", source)
        self.assertIn("DWave.draw_embedding(sampleset", source)
        self.assertIn('DWave.PythonCall.pyimport("matplotlib")', source)
        self.assertLess(
            source.index('DWave.PythonCall.pyimport("matplotlib")'),
            source.index("using Plots"),
        )
        self.assertIn('api_token = get(ENV, "DWAVE_API_TOKEN", "")', source)
        self.assertIn("DWave.Neal.Optimizer (SimulatedAnnealingSampler)", source)
        self.assertIn("QUBOTools.solution(QUBOTools.backend(qubo_model))", source)
        self.assertIn('repo-rev = "v0.7.6"', (REPO_ROOT / "notebooks_jl" / "Manifest.toml").read_text())
        self.assertNotIn("networkx_edges", source)
        self.assertNotIn("graph_from_edges", source)
        self.assertNotIn("graph_layout_subset", source)
        self.assertNotIn("sampler.to_networkx_graph()", source)
        self.assertNotIn("import PythonCall: pyconvert, pyimport", source)
        self.assertNotIn("using GraphPlot", source)
        self.assertNotIn("gplot(", source)
        self.assertNotIn("Graphs.grpah", source)
        self.assertNotIn("DW_2000Q_6", source)
        self.assertNotIn("Advantage_system1.1", source)
        self.assertNotIn("Advantage_system4.1", source)
        self.assertNotIn("DWave.dwave_networkx.chimera_graph", source)
        self.assertNotIn("DWave.dwave_networkx.pegasus_graph", source)
        self.assertNotIn('ENV["DWAVE_API_TOKEN"] = "<YOUR_KEY_HERE>";', source)
        self.assertNotIn("QUBOTools.sampleset", source)

    def test_python_topology_section_uses_current_sampler_topology(self) -> None:
        source = notebook_source(DWAVE_PYTHON_NOTEBOOK_PATH)

        self.assertIn('DWaveSampler(token=api_token, solver={"qpu": True})', source)
        self.assertIn('DWaveSampler(solver={"qpu": True})', source)
        self.assertIn('qpu.properties["topology"]', source)
        self.assertIn("qpu.to_networkx_graph()", source)
        self.assertIn("EmbeddingComposite(qpu)", source)
        self.assertIn('topology_type == "chimera"', source)
        self.assertIn('topology_type == "pegasus"', source)
        self.assertIn('topology_type == "zephyr"', source)
        self.assertIn("def draw_topology_graph(", source)
        self.assertIn("def draw_embedding_graph(", source)
        self.assertIn("Pegasus QPU topology (schematic layout)", source)
        self.assertNotIn('qpu.solver.id == "DW_2000Q_6"', source)
        self.assertNotIn("dwave_networkx", source)
        self.assertNotIn("dnx.", source)
        self.assertNotIn("dnx.chimera_graph", source)
        self.assertNotIn("dnx.pegasus_graph", source)

    def test_dwave_notebooks_explain_leap_token_setup_and_fallbacks(self) -> None:
        python_source = notebook_source(DWAVE_PYTHON_NOTEBOOK_PATH)
        julia_source = notebook_source(DWAVE_JULIA_NOTEBOOK_PATH)

        for source in (python_source, julia_source):
            self.assertIn("https://cloud.dwavesys.com/leap/", source)
            self.assertIn("DWAVE_API_TOKEN", source)
            self.assertIn("Leap dashboard", source)
            self.assertIn("SimulatedAnnealingSampler", source)
            self.assertNotIn('ENV["DWAVE_API_TOKEN"] = "<YOUR_KEY_HERE>"', source)

        self.assertIn('userdata.get("DWAVE_API_TOKEN")', python_source)
        self.assertIn('api_token = os.environ.get("DWAVE_API_TOKEN", "")', python_source)
        self.assertIn('os.environ["DWAVE_API_TOKEN"] = api_token', python_source)
        self.assertIn("!dwave ping", python_source)
        self.assertIn("Skipping `dwave ping` because DWAVE_API_TOKEN is not set", python_source)
        self.assertIn("DWavesampler = neal.SimulatedAnnealingSampler()", python_source)
        self.assertNotIn("!dwave setup", python_source)

        self.assertIn('api_token = get(ENV, "DWAVE_API_TOKEN", "")', julia_source)
        self.assertIn("DWave.Neal.Optimizer", julia_source)
        self.assertIn("Skipping D-Wave QPU topology plot", julia_source)
        self.assertIn("Skipping D-Wave QPU embedding plot", julia_source)

    def test_julia_embedding_plot_overlays_embedding_on_full_topology(self) -> None:
        source = notebook_cell_source(DWAVE_JULIA_NOTEBOOK_PATH, "function draw_embedding")

        self.assertIn("DWave.embedding(sampleset)", source)
        self.assertIn("DWave.WorkingGraph(QUBOTools.metadata(sampleset))", source)
        self.assertIn("DWave.draw_embedding(sampleset; node_size=2)", source)
        self.assertIn("$(length(arch.nodes))-qubit working graph", source)
        self.assertNotIn("graph_layout_subset", source)
        self.assertNotIn("nodefillc = fill", source)
        self.assertNotIn("gplot(", source)

    def test_julia_quantum_annealer_output_analysis_matches_python_views(self) -> None:
        julia_source = notebook_cell_source(DWAVE_JULIA_NOTEBOOK_PATH, "qpu_solution = QUBOTools.solution")
        python_source = notebook_cell_source(DWAVE_PYTHON_NOTEBOOK_PATH, "plot_enumerate(DWaveSamples")

        self.assertIn("QUBOTools.solution(QUBOTools.backend(qubo_model))", julia_source)
        self.assertIn("QUBOTools.EnergyDistributionPlot(qpu_solution)", julia_source)
        self.assertIn("QUBOTools.EnergyFrequencyPlot(qpu_solution)", julia_source)
        self.assertIn("display(plot(QUBOTools.EnergyDistributionPlot", julia_source)
        self.assertLess(
            julia_source.index("QUBOTools.EnergyDistributionPlot(qpu_solution)"),
            julia_source.index("QUBOTools.EnergyFrequencyPlot(qpu_solution)"),
        )
        self.assertIn("plot_enumerate(DWaveSamples", python_source)
        self.assertIn("plot_energies(DWaveSamples", python_source)

    def test_live_dwave_outputs_are_refreshed_without_duplicate_julia_plot_formats(self) -> None:
        julia_notebook = json.loads(DWAVE_JULIA_NOTEBOOK_PATH.read_text())
        python_notebook = json.loads(DWAVE_PYTHON_NOTEBOOK_PATH.read_text())

        julia_markers = (
            "DWave.dwave_system.DWaveSampler",
            "qpu_solution = QUBOTools.solution",
            "function draw_topology",
            "function draw_embedding",
        )
        python_markers = (
            'qpu = DWaveSampler(token=api_token, solver={"qpu": True})',
            "EmbeddingComposite(qpu)",
        )

        julia_cells = [
            cell
            for cell in julia_notebook["cells"]
            if any(marker in "".join(cell.get("source", [])) for marker in julia_markers)
        ]
        python_cells = [
            cell
            for cell in python_notebook["cells"]
            if any(marker in "".join(cell.get("source", [])) for marker in python_markers)
        ]

        self.assertEqual(len(julia_cells), len(julia_markers))
        self.assertEqual(len(python_cells), len(python_markers))

        for cell in julia_cells + python_cells:
            self.assertIsNotNone(cell.get("execution_count"))

        analysis_image_outputs = [
            output
            for output in julia_cells[1].get("outputs", [])
            if "image/png" in output.get("data", {})
        ]
        self.assertGreaterEqual(len(analysis_image_outputs), 2)
        self.assertTrue(julia_cells[2].get("outputs"))
        self.assertTrue(julia_cells[3].get("outputs"))
        self.assertTrue(python_cells[0].get("outputs"))

        for cell in julia_notebook["cells"]:
            for output in cell.get("outputs", []):
                data = output.get("data", {})
                if "image/png" in data:
                    self.assertEqual(set(data), {"image/png"})
