"""Behavioral and parsed notebook artifact contracts."""

from __future__ import annotations

import ast
import io
import json
import math
import re
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import numpy as np

from notebook_test_support import (
    BENCHMARKING_JULIA_NOTEBOOK_PATH,
    BENCHMARKING_PYTHON_NOTEBOOK_PATH,
    BENCHMARKING_RESULTS_ARCHIVES,
    DWAVE_JULIA_NOTEBOOK_PATH,
    DWAVE_PYTHON_NOTEBOOK_PATH,
    GAMA_JULIA_NOTEBOOK_PATH,
    GAMA_NOTEBOOK_PATH,
    MATHPROG_JULIA_NOTEBOOK_PATH,
    MATHPROG_NOTEBOOK_PATH,
    QCI_NOTEBOOK_PATH,
    QUBO_JULIA_NOTEBOOK_PATH,
    QUBO_NOTEBOOK_PATH,
    REPO_ROOT,
    notebook_cell_source,
    notebook_function_definitions,
    notebook_function_source,
    notebook_output_text,
    notebook_paths,
    notebook_solution_output_texts,
)


class NotebookSourceSafetyTests(unittest.TestCase):
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

    def test_qci_python_outputs_omit_provider_identifiers(self) -> None:
        output = notebook_output_text(QCI_NOTEBOOK_PATH)

        self.assertNotRegex(output, re.compile(r"(?i)job[_ -]?id"))
        self.assertNotRegex(output, re.compile(r"(?i)file[_ -]?id"))
        self.assertNotRegex(output, re.compile(r"(?i)bearer\s+[a-z0-9._-]+"))

    def test_qci_python_solve_suppresses_identifiers_from_both_streams(self) -> None:
        cell_source = notebook_cell_source(
            QCI_NOTEBOOK_PATH,
            "def solve_without_provider_identifiers",
        )
        function_node = next(
            node
            for node in ast.parse(cell_source).body
            if isinstance(node, ast.FunctionDef)
            and node.name == "solve_without_provider_identifiers"
        )
        function_source = ast.get_source_segment(cell_source, function_node)
        assert function_source is not None
        namespace = {
            "io": io,
            "redirect_stderr": redirect_stderr,
            "redirect_stdout": redirect_stdout,
        }
        exec(function_source, namespace)

        class IdentifierPrintingSolver:
            def solve(self, model, **kwargs):
                print("job_id: provider-job-123")
                print("file_id: provider-file-456", file=sys.stderr)
                return model, kwargs

        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            response = namespace["solve_without_provider_identifiers"](
                IdentifierPrintingSolver(),
                "model",
                num_samples=10,
            )

        self.assertEqual(("model", {"num_samples": 10}), response)
        self.assertEqual(
            "QCI job completed; provider identifiers are omitted from notebook output.\n",
            stdout.getvalue(),
        )
        self.assertEqual("", stderr.getvalue())


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


class BenchmarkingNotebookArchiveTests(unittest.TestCase):
    def test_committed_results_archives_use_shared_json_cache(self) -> None:
        expected_names = ["all_results.json", "results_42.json"]

        for archive_path in BENCHMARKING_RESULTS_ARCHIVES:
            with self.subTest(archive=archive_path.relative_to(REPO_ROOT).as_posix()):
                self.assertTrue(archive_path.is_file())

                with zipfile.ZipFile(archive_path) as archive:
                    self.assertEqual(expected_names, sorted(archive.namelist()))
                    all_results = json.loads(archive.read("all_results.json"))
                    single_results = json.loads(archive.read("results_42.json"))

                metric_keys = {"tts", "ttsci", "ttt", "tttci"}
                self.assertEqual(
                    {"tts", "ttsci"},
                    set(single_results).intersection(metric_keys),
                )

                first_instance = all_results[sorted(all_results, key=int)[0]]
                self.assertEqual(
                    {"tts", "ttsci"},
                    set(first_instance).intersection(metric_keys),
                )

    def test_python_cache_helpers_round_trip_values_and_legacy_layouts(self) -> None:
        namespace = {"json": json, "math": math, "np": np}
        exec(
            notebook_function_definitions(
                BENCHMARKING_PYTHON_NOTEBOOK_PATH,
                "def benchmark_cache_to_json",
                {
                    "benchmark_cache_to_json",
                    "benchmark_cache_from_json",
                    "normalize_single_results_cache",
                    "schedule_boot_to_boot_schedule",
                    "boot_schedule_to_schedule_boot",
                    "unwrap_default_sweep",
                    "normalize_all_results_cache",
                    "load_benchmark_cache",
                    "save_benchmark_cache",
                },
            ),
            namespace,
        )

        payload = {2: np.array([1.0, np.inf, -np.inf, np.nan])}
        encoded = namespace["benchmark_cache_to_json"](payload)
        self.assertEqual({"2": [1.0, "Infinity", "-Infinity", "NaN"]}, encoded)
        decoded = namespace["benchmark_cache_from_json"](encoded)
        self.assertEqual([1.0, np.inf, -np.inf], decoded[2][:3])
        self.assertTrue(np.isnan(decoded[2][3]))

        boot_schedule = {
            0: {"geometric": [1, 2]},
            1: {"linear": [3, 4]},
        }
        schedule_boot = namespace["boot_schedule_to_schedule_boot"](boot_schedule)
        self.assertEqual(
            {"geometric": {0: [1, 2]}, "linear": {1: [3, 4]}},
            schedule_boot,
        )
        self.assertEqual(
            boot_schedule,
            namespace["schedule_boot_to_boot_schedule"](schedule_boot),
        )

        with tempfile.TemporaryDirectory() as tmp_name:
            cache_path = Path(tmp_name) / "results.json"
            namespace["save_benchmark_cache"](
                cache_path,
                {"ttt": [1.5], "tttci": [1.0, 2.0]},
            )
            restored = namespace["load_benchmark_cache"](cache_path, "single")
            with self.assertRaises(ValueError):
                namespace["load_benchmark_cache"](cache_path, "unknown")

        self.assertEqual({"tts": [1.5], "ttsci": [1.0, 2.0]}, restored)


class PythonNotebookHelperTests(unittest.TestCase):
    def test_plot_labels_are_sparse_and_bounded(self) -> None:
        namespace = {"np": np}
        exec(
            notebook_function_definitions(
                QUBO_NOTEBOOK_PATH,
                "def sparse_tick_positions",
                {"sparse_tick_positions", "binary_sample_label"},
            ),
            namespace,
        )

        self.assertEqual([0, 1, 2, 3], namespace["sparse_tick_positions"](4).tolist())
        self.assertEqual(
            [0, 6, 12, 19],
            namespace["sparse_tick_positions"](20, max_ticks=4).tolist(),
        )
        sample = {index: index % 2 for index in range(10)}
        self.assertEqual(
            "0101010101",
            namespace["binary_sample_label"](sample, range(10), max_length=10),
        )
        self.assertEqual(
            "01...01",
            namespace["binary_sample_label"](sample, range(10), max_length=7),
        )

    def test_topology_helpers_derive_layout_and_titles(self) -> None:
        namespace = {"np": np}
        exec(
            notebook_function_definitions(
                DWAVE_PYTHON_NOTEBOOK_PATH,
                "def topology_position_map",
                {"topology_position_map", "topology_title"},
            ),
            namespace,
        )

        class Graph:
            def __init__(self, nodes):
                self._nodes = nodes

            def nodes(self):
                return self._nodes

        self.assertEqual({}, namespace["topology_position_map"](Graph([])))
        self.assertEqual(
            {1: (0, 0), 10: (1, 0), 2: (0, -1)},
            namespace["topology_position_map"](Graph([10, 2, 1])),
        )
        self.assertEqual(
            {
                "chimera": "Chimera QPU topology (schematic layout)",
                "pegasus": "Pegasus QPU topology (schematic layout)",
                "zephyr": "Zephyr QPU topology (schematic layout)",
                None: "D-Wave QPU topology (schematic layout)",
            },
            {
                topology: namespace["topology_title"](topology)
                for topology in ("chimera", "pegasus", "zephyr", None)
            },
        )


class BenchmarkingNotebookScopeTests(unittest.TestCase):
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
