"""Optimization invariants and optional-runtime guards, without requiring CUDA-Q.

The two-variable fixture is the notebook's penalty exercise. Costs use arbitrary
objective units; dividing by the reference energy makes Pauli coefficients [-].
"""

import ast
import builtins
import contextlib
import copy
import importlib.util
import io
import itertools
import json
import os
import sys
import unittest
import warnings
from types import SimpleNamespace
from unittest.mock import patch

from notebook_test_support import (
    DWAVE_PYTHON_NOTEBOOK_PATH,
    REPO_ROOT,
    notebook_cell_source,
    notebook_function_definitions,
    verify_notebooks,
)


class PenaltyExercise:
    """Ising representation of x0 + 2*x1 + 4*(x0+x1-1)^2, in cost units."""

    def __len__(self):
        return 2

    def to_ising(self):
        return {0: 0.5, 1: 1.0}, {(0, 1): 2.0}, 3.5


class CostConventionTests(unittest.TestCase):
    def test_pauli_energies_match_penalty_objective_for_every_assignment(self):
        namespace = {}
        exec(notebook_function_definitions(
            DWAVE_PYTHON_NOTEBOOK_PATH, "def ising_cost_data", {"ising_cost_data"}
        ), namespace)
        for reference_energy in (1.0, 4.0):
            fields, left, right, couplings, offset = namespace["ising_cost_data"](
                PenaltyExercise(), reference_energy
            )
            energies = {}
            for bits in itertools.product((0, 1), repeat=2):
                z = [1 - 2 * bit for bit in bits]
                normalized = offset + sum(field * spin for field, spin in zip(fields, z))
                normalized += sum(coefficient * z[i] * z[j] for i, j, coefficient in zip(left, right, couplings))
                expected = bits[0] + 2 * bits[1] + 4 * (sum(bits) - 1) ** 2
                self.assertAlmostEqual(expected, normalized * reference_energy)
                energies[bits] = normalized
            self.assertEqual((1, 0), min(energies, key=energies.get))
        for reference_energy in (0, -1):
            with self.subTest(reference_energy=reference_energy), self.assertRaises(ValueError):
                namespace["ising_cost_data"](PenaltyExercise(), reference_energy)


class OptionalCudaqTests(unittest.TestCase):
    def test_import_filters_only_the_exact_cudaq_016_notice(self):
        """Keep other categories, changed notices, and warnings after import visible."""
        notice = (
            "The CUDA-Q `sample` and `observe` algorithmic primitives will change in "
            "a future release. Existing code may require updates. See "
            "https://nvidia.github.io/cuda-quantum/latest/using/migration/"
            "upcoming_changes.html for details."
        )
        original_import = builtins.__import__
        cudaq = SimpleNamespace(set_target=lambda target: None, set_random_seed=lambda seed: None)

        def import_with_notices(name, *args, **kwargs):
            if name == "cudaq":
                warnings.warn(notice, FutureWarning)
                warnings.warn(notice, UserWarning)
                warnings.warn(notice + " Additional detail.", FutureWarning)
                warnings.warn("Unrelated future warning", FutureWarning)
                return cudaq
            return original_import(name, *args, **kwargs)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with patch("builtins.__import__", side_effect=import_with_notices):
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(notebook_cell_source(DWAVE_PYTHON_NOTEBOOK_PATH, "CUDAQ_SKIP_MESSAGE ="), {})
            warnings.warn(notice, FutureWarning)
        self.assertEqual(
            [(notice, UserWarning), (notice + " Additional detail.", FutureWarning),
             ("Unrelated future warning", FutureWarning), (notice, FutureWarning)],
            [(str(item.message), item.category) for item in caught],
        )

    def execute_import(self, missing_name, required):
        original_import = builtins.__import__
        attempted = []

        def unavailable(name, *args, **kwargs):
            if name == "cudaq":
                attempted.append(name)
                raise ModuleNotFoundError(f"No module named {missing_name!r}", name=missing_name)
            return original_import(name, *args, **kwargs)

        output = io.StringIO()
        namespace = {}
        with patch("builtins.__import__", side_effect=unavailable):
            with patch.dict(os.environ, {"QUBONOTEBOOKS_CUDAQ_REQUIRE": str(int(required))}):
                with contextlib.redirect_stdout(output):
                    exec(notebook_cell_source(DWAVE_PYTHON_NOTEBOOK_PATH, "CUDAQ_SKIP_MESSAGE ="), namespace)
        self.assertEqual(["cudaq"], attempted)
        return namespace, output.getvalue()

    def test_missing_optional_package_produces_one_skip_notice(self):
        namespace, output = self.execute_import("cudaq", False)
        self.assertFalse(namespace["HAS_CUDAQ"])
        self.assertEqual(1, len(output.splitlines()))
        self.assertIn("Skipping CUDA-Q", output)

    def test_required_package_cannot_silently_skip(self):
        with self.assertRaises(ModuleNotFoundError) as caught:
            self.execute_import("cudaq", True)
        self.assertEqual("cudaq", caught.exception.name)

    def test_broken_installation_does_not_become_an_optional_skip(self):
        with self.assertRaises(ModuleNotFoundError) as caught:
            self.execute_import("cupy", False)
        self.assertEqual("cupy", caught.exception.name)


class OptimizationVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("verify_cudaq", REPO_ROOT / "scripts/verify_cudaq.py")
        cls.verifier = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"verify_notebooks": verify_notebooks}):
            spec.loader.exec_module(cls.verifier)

    def notebook(self):
        return {"cells": [
            {"metadata": {"tags": [tag]}, "execution_count": 1,
             "outputs": [{"output_type": "stream", "text": [message + "\n"]}]}
            for tag, message in (
                ("cudaq-annealing-result", "CUDA-Q quantum annealing checks passed."),
                ("cudaq-qaoa-results", "CUDA-Q QAOA checks passed."),
            )
        ]}

    def test_accepts_executed_optimization_completion(self):
        self.verifier.require_optimization_result(self.notebook())

    def test_rejects_a_skipped_unexecuted_or_missing_optimization_section(self):
        complete = self.notebook()
        for section in (0, 1):
            for defect in ("missing", "unexecuted", "untagged", "skipped", "wrong-method"):
                notebook = copy.deepcopy(complete)
                cell = notebook["cells"][section]
                if defect == "missing":
                    notebook["cells"].pop(section)
                elif defect == "unexecuted":
                    cell["execution_count"] = None
                elif defect == "untagged":
                    cell["metadata"]["tags"] = []
                elif defect == "skipped":
                    cell["outputs"][0]["text"] = ["Skipping CUDA-Q quantum methods.\n"]
                else:
                    cell["outputs"] = copy.deepcopy(complete["cells"][1 - section]["outputs"])
                with self.subTest(section=section, defect=defect), self.assertRaises(RuntimeError):
                    self.verifier.require_optimization_result(notebook)


class AnnealPresentationTests(unittest.TestCase):
    def test_saved_results_follow_an_enabled_import(self):
        """Published quantum results must belong to an enabled execution."""
        notebook = json.loads(DWAVE_PYTHON_NOTEBOOK_PATH.read_text())
        availability = next(cell for cell in notebook["cells"]
                            if "CUDAQ_SKIP_MESSAGE =" in "".join(cell["source"]))
        output = "".join("".join(item.get("text", [])) for item in availability["outputs"])
        self.assertIn("CUDA-Q enabled: qpp-cpu", output)
        self.assertNotIn("Skipping CUDA-Q", output)

    def test_sampling_keeps_selected_anneal_state_and_probability_paired(self):
        """Reordered dimensionless times and a reused loop variable cannot change the selected run."""
        import numpy as np

        table_display = SimpleNamespace(DataFrame=lambda rows: SimpleNamespace(to_string=lambda **kwargs: ""))

        for times in ([0.0, 2.0, 10.0, 50.0, 200.0], [0.0, 200.0, 2.0, 50.0, 10.0]):
            with self.subTest(times=times):
                states = {}
                sampled = []

                def get_state(kernel, *args):
                    # Synthetic normalized amplitudes [-], indexed by time [-].
                    total_time = args[-2]
                    probability = 0.25 + 0.65 * total_time / 200
                    state = np.sqrt([(1 - probability) / 3, probability,
                                     (1 - probability) / 3, (1 - probability) / 3])
                    states[total_time] = state
                    return state

                def sample(kernel, state, shots_count):
                    sampled.append(state)
                    optimal = round(float(state[1] ** 2) * shots_count)
                    return {"10": optimal, "01": shots_count - optimal}

                cudaq = SimpleNamespace(
                    kernel=lambda function: function, State=np.ndarray,
                    observe=lambda *args: SimpleNamespace(expectation=lambda: -2),
                    get_state=get_state, sample=sample,
                )
                namespace = dict(
                    HAS_CUDAQ=True, cudaq=cudaq, np=np, pd=table_display, n_qubits=2,
                    fields=[], pair_left=[], pair_right=[], couplings=[], mixer_hamiltonian=None,
                    ground_mask=np.array([False, True, False, False]),
                    feasible_mask=np.array([False, True, True, False]),
                    # Same penalty exercise as above; all energies in cost units.
                    qubo_energies=np.array([4, 1, 2, 7]), ground_energy=1,
                    c=np.array([1, 2]), A=np.array([[1, 1]]), b=np.array([1]), rho=4,
                )
                tree = ast.parse(notebook_cell_source(DWAVE_PYTHON_NOTEBOOK_PATH, "def quantum_anneal"))
                time_loop = next(node for node in ast.walk(tree)
                                 if isinstance(node, ast.For) and isinstance(node.target, ast.Name)
                                 and node.target.id == "total_time")
                time_loop.iter = ast.parse(repr(times), mode="eval").body
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(ast.fix_missing_locations(tree), "<anneal-cell>", "exec"), namespace)
                    # A later exploratory cell reuses the former loop variable.
                    namespace["final_state"] = states[0.0]
                    exec(notebook_cell_source(DWAVE_PYTHON_NOTEBOOK_PATH, "shots = 4096"), namespace)
                self.assertIs(states[200.0], sampled[0])
                self.assertAlmostEqual(0.9, namespace["success_probability"])
