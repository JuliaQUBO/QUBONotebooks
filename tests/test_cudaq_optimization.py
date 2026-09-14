"""Optimization invariants and optional-runtime guards, without requiring CUDA-Q.

The two-variable fixture is the notebook's penalty exercise. Costs use arbitrary
objective units; dividing by the reference energy makes Pauli coefficients [-].
"""

import builtins
import contextlib
import importlib.util
import io
import itertools
import os
import sys
import unittest
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


class OptionalCudaqTests(unittest.TestCase):
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

    def notebook(self, text, execution_count=1, tags=("cudaq-optimization-result",)):
        return {"cells": [{"metadata": {"tags": list(tags)}, "execution_count": execution_count,
                           "outputs": [{"output_type": "stream", "text": [text]}]}]}

    def test_accepts_executed_optimization_completion(self):
        self.verifier.require_optimization_result(self.notebook("CUDA-Q optimization checks passed.\n"))

    def test_rejects_a_skipped_unexecuted_or_missing_optimization_section(self):
        for notebook in (
            self.notebook("Skipping CUDA-Q quantum annealing.\n"),
            self.notebook("CUDA-Q optimization checks passed.\n", execution_count=None),
            self.notebook("CUDA-Q optimization checks passed.\n", tags=()),
            {"cells": []},
        ):
            with self.subTest(notebook=notebook), self.assertRaises(RuntimeError):
                self.verifier.require_optimization_result(notebook)
