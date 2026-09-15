"""QAOA mapping, optional-import guards, and real CPU kernel invariants.

The default docs environment exercises pure checks and import guards. The
optional CUDA-Q CI lane additionally checks the real compiled two-layer kernel
against an independent dense-matrix reference and checks measurement bit order.
"""

import ast
import builtins
import contextlib
import importlib.util
import io
import itertools
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from notebook_test_support import (
    QUBO_NOTEBOOK_PATH, REPO_ROOT, notebook_function_definitions, verify_notebooks,
)


def section_cells():
    return [cell for cell in json.loads(QUBO_NOTEBOOK_PATH.read_text())["cells"]
            if any(tag.startswith("cudaq-qaoa-") for tag in cell.get("metadata", {}).get("tags", []))]


def cell_source(tag):
    return "".join(next(cell for cell in section_cells()
                        if tag in cell["metadata"]["tags"])["source"])


class PenaltyFixture:
    """x0 + 2*x1 + 4*(x0+x1-1)^2 in arbitrary objective units."""

    def __len__(self):
        return 2

    def to_ising(self):
        return {0: 0.5, 1: 1.0}, {(0, 1): 2.0}, 3.5


class MappingTests(unittest.TestCase):
    def test_fields_pairs_and_offset_match_original_penalty_cost(self):
        namespace = {}
        exec(notebook_function_definitions(
            QUBO_NOTEBOOK_PATH, "def qaoa_cost_data", {"qaoa_cost_data"}
        ), namespace)
        convert = namespace["qaoa_cost_data"]
        for scale in (1.0, 4.0):
            fields, left, right, pairs, offset = convert(PenaltyFixture(), scale)
            for bits in itertools.product((0, 1), repeat=2):
                z = [1 - 2 * bit for bit in bits]
                raw = sum(a * spin for a, spin in zip(fields, z))
                raw += sum(a * z[i] * z[j] for i, j, a in zip(left, right, pairs))
                self.assertAlmostEqual(bits[0] + 2 * bits[1] + 4 * (sum(bits) - 1) ** 2,
                                       scale * (raw + offset))
        for scale in (0, -1):
            with self.assertRaises(ValueError):
                convert(PenaltyFixture(), scale)


class OptionalImportTests(unittest.TestCase):
    def run_section(self, missing_name, required=False):
        original_import = builtins.__import__
        attempted = []

        def missing_import(name, *args, **kwargs):
            if name == "cudaq":
                attempted.append(name)
                raise ModuleNotFoundError(f"No module named {missing_name!r}", name=missing_name)
            return original_import(name, *args, **kwargs)

        namespace = {}
        output = io.StringIO()
        with patch("builtins.__import__", side_effect=missing_import):
            with patch.dict(os.environ, {"QUBONOTEBOOKS_CUDAQ_REQUIRE": str(int(required))}):
                with contextlib.redirect_stdout(output):
                    for cell in section_cells():
                        if cell["cell_type"] == "code":
                            exec("".join(cell["source"]), namespace)
        self.assertEqual(["cudaq"], attempted)
        return namespace, output.getvalue()

    def test_entire_section_skips_once_without_optional_package(self):
        namespace, output = self.run_section("cudaq")
        self.assertFalse(namespace["HAS_CUDAQ"])
        self.assertEqual("Skipping CUDA-Q QAOA: install the optional cudaq group.\n", output)
        self.assertNotIn("qaoa", namespace)
        self.assertNotIn("sample_rows", namespace)

    def test_required_and_broken_installations_fail(self):
        for name, required in (("cudaq", True), ("cupy", False)):
            with self.subTest(name=name, required=required):
                with self.assertRaises(ModuleNotFoundError) as caught:
                    self.run_section(name, required)
                self.assertEqual(name, caught.exception.name)

    def test_published_section_records_only_the_skip_execution(self):
        cells = [cell for cell in section_cells() if cell["cell_type"] == "code"]
        self.assertEqual(5, len(cells))
        self.assertTrue(all(cell["execution_count"] is not None for cell in cells))
        outputs = [output for cell in cells for output in cell["outputs"]]
        self.assertEqual(1, len(outputs))
        self.assertEqual("Skipping CUDA-Q QAOA: install the optional cudaq group.\n",
                         "".join(outputs[0]["text"]))


@unittest.skipUnless(importlib.util.find_spec("cudaq"), "optional CUDA-Q CPU lane")
class KernelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="qaoa-kernel-test-")
        cls.addClassCleanup(cls.tmp.cleanup)
        tree = ast.parse(cell_source("cudaq-qaoa-ansatz"))
        kernel = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef) and node.name == "qaoa")
        # A real file lets CUDA-Q inspect the same notebook kernel's source.
        path = Path(cls.tmp.name) / "qaoa_notebook_kernel.py"
        path.write_text("import numpy as np\n" + cell_source("cudaq-qaoa-import") + "\n"
                        + ast.unparse(kernel) + "\n")
        spec = importlib.util.spec_from_file_location("qaoa_notebook_kernel", path)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        cls.addClassCleanup(sys.modules.pop, spec.name, None)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(cls.module)

    def reference(self, p):
        from scipy.linalg import expm

        fields, left, right, pairs = [0.37, -0.81], [0], [1], [0.53]
        parameters = [0.23, -0.47, 0.31, 0.62] if p == 2 else [0.23, 0.31] if p == 1 else []
        z = np.diag([1, -1])
        identity = np.eye(2)
        x = np.array([[0, 1], [1, 0]])
        # Explicit little-endian basis: |x1 x0>, independent of the gate sequence.
        cost = fields[0] * np.kron(identity, z) + fields[1] * np.kron(z, identity)
        cost += pairs[0] * np.kron(z, z)
        mixer = np.kron(identity, x) + np.kron(x, identity)
        state = np.ones(4, dtype=complex) / 2
        for layer in range(p):
            state = expm(-1j * parameters[p + layer] * mixer) @ (
                expm(-1j * parameters[layer] * cost) @ state
            )
        return (2, p, fields, left, right, pairs, parameters), state, cost

    def test_compiled_layers_match_dense_exponentials_and_expectation(self):
        cudaq = self.module.cudaq
        for p in (0, 1, 2):
            with self.subTest(p=p):
                args, expected, cost = self.reference(p)
                actual = np.asarray(cudaq.get_state(self.module.qaoa, *args))
                np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-10)
                operator = (0.37 * cudaq.spin.z(0) - 0.81 * cudaq.spin.z(1)
                            + 0.53 * cudaq.spin.z(0) * cudaq.spin.z(1))
                observed = cudaq.observe(self.module.qaoa, operator, *args).expectation()
                self.assertAlmostEqual(float(np.vdot(expected, cost @ expected).real), observed)

    def test_measurement_bitstrings_map_to_reference_state_probabilities(self):
        cudaq = self.module.cudaq
        args, state, cost = self.reference(2)
        probabilities = abs(state) ** 2
        shots = 16384
        for seed in (17, 314159):
            cudaq.set_random_seed(seed)
            counts = dict(cudaq.sample(self.module.qaoa, *args, shots_count=shots).items())
            self.assertEqual(shots, sum(counts.values()))
            for index, probability in enumerate(probabilities):
                bitstring = "".join(str((index >> i) & 1) for i in range(2))
                # Six standard deviations plus a discrete-count margin.
                tolerance = 6 * np.sqrt(probability * (1 - probability) / shots) + 1 / shots
                self.assertLess(abs(counts.get(bitstring, 0) / shots - probability), tolerance)

    def test_notebook_reports_correct_costs_feasibility_and_probabilities(self):
        import dimod
        import pandas as pd

        model = dimod.BinaryQuadraticModel({0: -3, 1: -2}, {(0, 1): 8}, 4, dimod.BINARY)
        args = (2, 2, [-0.125, -0.25], [0], [1], [0.5])
        parameters = [0.23, -0.47, 0.31, 0.62]
        cudaq = self.module.cudaq
        probabilities = abs(np.asarray(cudaq.get_state(self.module.qaoa, *args, parameters))) ** 2
        namespace = dict(
            HAS_CUDAQ=True, cudaq=cudaq, np=np, pd=pd, model=model,
            qaoa=self.module.qaoa, qaoa_args=args, optimal_parameters=parameters,
            probabilities=probabilities, energy_scale=4.0, ising_offset=0.875,
            rho=4, A=np.array([[1, 1]]), b=np.array([1]),
            qubo_linear_cost=np.array([1, 2]), ground_energy=1,
        )
        with contextlib.redirect_stdout(io.StringIO()):
            exec(cell_source("cudaq-qaoa-results"), namespace)
        expected = {"00": (4, 0, False, probabilities[0]),
                    "10": (1, 1, True, probabilities[1]),
                    "01": (2, 2, True, probabilities[2]),
                    "11": (7, 3, False, probabilities[3])}
        self.assertEqual(4, len(namespace["sample_rows"]))
        for row in namespace["sample_rows"]:
            cost, original, feasible, probability = expected[row["bits (x0 first)"]]
            self.assertEqual(cost, row["QUBO cost"])
            self.assertEqual(original, row["original cost"])
            self.assertEqual(feasible, row["feasible"])
            self.assertAlmostEqual(cost / 4 - 0.875, row["raw Ising"])
            self.assertAlmostEqual(probability, row["exact probability"])
            self.assertEqual(row["count"] / 8192, row["sample frequency"])
        self.assertEqual("10", namespace["best_sample"]["bits (x0 first)"])
        self.assertEqual(max(row["count"] for row in namespace["sample_rows"]),
                         namespace["most_frequent"]["count"])


class CoverageTests(unittest.TestCase):
    def test_verifier_default_executes_and_requires_both_optimization_results(self):
        spec = importlib.util.spec_from_file_location("verify_cudaq", REPO_ROOT / "scripts/verify_cudaq.py")
        verifier = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"verify_notebooks": verify_notebooks}):
            spec.loader.exec_module(verifier)
        expected = ["notebooks_py/2-QUBO_python.ipynb", "notebooks_py/4-DWAVE_python.ipynb"]
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)
            complete = {"cells": [{"execution_count": 1,
                                  "metadata": {"tags": ["cudaq-optimization-result"]},
                                  "outputs": [{"output_type": "stream",
                                               "text": ["CUDA-Q optimization checks passed.\n"]}]}]}
            for name in expected:
                (output_dir / Path(name).name).write_text(json.dumps(complete))
            with (
                patch.object(sys, "argv", ["verify_cudaq.py"]),
                patch.dict(os.environ, {}, clear=False),
                patch.object(verify_notebooks, "parse_args",
                             side_effect=lambda: SimpleNamespace(notebooks=sys.argv[1:])),
                patch.object(verify_notebooks, "main", return_value=0) as run,
                patch.object(verify_notebooks, "output_dir", return_value=output_dir),
            ):
                self.assertEqual(0, verifier.main())
                self.assertEqual(expected, sys.argv[1:])
                self.assertEqual("1", os.environ["QUBONOTEBOOKS_CUDAQ_REQUIRE"])
                run.assert_called_once_with()
                for name in expected:
                    result = output_dir / Path(name).name
                    result.write_text('{"cells": []}')
                    with self.subTest(name=name), self.assertRaises(RuntimeError):
                        verifier.main()
                    result.write_text(json.dumps(complete))

    def test_workflow_triggers_both_notebooks_on_prs_and_main(self):
        import yaml

        workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/cudaq-python.yml").read_text())
        events = workflow.get("on", workflow.get(True))
        for event in ("pull_request", "push"):
            self.assertIn("notebooks_py/2-QUBO_python.ipynb", events[event]["paths"])
            self.assertIn("notebooks_py/4-DWAVE_python.ipynb", events[event]["paths"])
        steps = workflow["jobs"]["cpu"]["steps"]
        self.assertTrue(any("test_cudaq_qaoa.py" in step.get("run", "") for step in steps))
