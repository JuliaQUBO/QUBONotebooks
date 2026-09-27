"""Exercise the ensemble analysis with real cached samples and known energies.

Energies use arbitrary Ising units; shot counts and performance ratios are
dimensionless. Constant-energy samples give exact expected ratios without
duplicating the bootstrap calculation.
"""

from __future__ import annotations

import importlib.util
import os
import pickle
import tempfile
import time
import unittest
import warnings
from pathlib import Path

from notebook_test_support import (
    BENCHMARKING_PYTHON_NOTEBOOK_PATH,
    notebook_cell_source,
    notebook_function_definitions,
)


HAS_BACKENDS = all(
    importlib.util.find_spec(name) is not None
    for name in ("numpy", "scipy", "matplotlib", "dimod", "neal")
)


@unittest.skipUnless(HAS_BACKENDS, "requires the docs and qubo dependency groups")
class BenchmarkingBootstrapTests(unittest.TestCase):
    def run_ensemble(self, shots, *, cold=False):
        import dimod
        import neal
        import matplotlib
        import numpy as np
        from scipy import stats

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        namespace = {
            "np": np, "stats": stats, "plt": plt, "os": os,
            "pickle": pickle, "dimod": dimod, "N": 3, "time": time,
            "simAnnSampler": neal.SimulatedAnnealingSampler(),
            # An unrelated model exposes accidental reuse on a cache miss.
            "model_random": dimod.BinaryQuadraticModel.from_ising({0: 100.0}, {}),
        }
        exec(
            notebook_function_definitions(
                BENCHMARKING_PYTHON_NOTEBOOK_PATH,
                "def bootstrap(",
                {"bootstrap", "tsplotboot"},
            ),
            namespace,
        )
        with tempfile.TemporaryDirectory() as cache:
            # Two instances choose different best sweeps. The fixed-sweep
            # energies are -2 and -4, giving ratios 0.5 and 1 against [-4, 0].
            for instance in (() if cold else range(2)):
                for sweep, energy in ((10, -2.0), (1000, -4.0)):
                    samples = dimod.SampleSet.from_samples(
                        np.ones((1000, 1), dtype=int), dimod.SPIN, energy=energy,
                        info={"timing": 0.1},  # Seconds; this cell uses cached energies.
                    )
                    with (Path(cache) / f"ensemble_{instance}_geometric_{sweep}.p").open("wb") as stream:
                        pickle.dump(samples, stream)
            namespace.update(
                instances=range(2), schedules=["geometric"],
                sweeps=[10, 1000], min_median_sweep=10, indices=[0, 1],
                total_reads=1000, shots=shots, pickle_path=cache,
                all_results={
                    i: {"min_energy": {"geometric": -4.0}, "random_energy": {"geometric": 0.0}}
                    for i in range(2)
                },
            )
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", RuntimeWarning)
                    exec(
                        notebook_cell_source(
                            BENCHMARKING_PYTHON_NOTEBOOK_PATH,
                            "all_approx_ratio = {}",
                        ),
                        namespace,
                    )
                if cold:
                    # Reconstruct each specified Ising instance independently
                    # and evaluate the saved bitstrings in its original model.
                    for instance in range(2):
                        rng = np.random.RandomState(instance)
                        coupling = np.triu(2 * rng.rand(3, 3) - 1, 1)
                        field = 2 * rng.rand(3) - 1
                        model = dimod.BinaryQuadraticModel.from_ising(field, coupling)
                        for sweep in (10, 1000):
                            path = Path(cache) / f"ensemble_{instance}_geometric_{sweep}.p"
                            with path.open("rb") as stream:
                                samples = pickle.load(stream)
                            np.testing.assert_allclose(
                                samples.record.energy, model.energies(samples),
                                rtol=1e-12, atol=1e-12,
                            )
            finally:
                plt.close("all")
        return namespace["all_approx_ratio"]

    def test_shot_counts_can_exceed_bootstrap_repetitions(self):
        import numpy as np

        shots = [1, 100, 101, 999]
        results = self.run_ensemble(shots)
        for instance in results.values():
            np.testing.assert_array_equal(instance["geometric"][10], [0.5] * len(shots))
            np.testing.assert_array_equal(instance["geometric"][1000], [1.0] * len(shots))

    def test_missing_sample_cache_uses_each_instances_model(self):
        self.run_ensemble([1, 2], cold=True)

    def test_demonstration_samplers_are_repeatable(self):
        import contextlib
        import io
        import dimod
        import neal
        import numpy as np

        model = dimod.BinaryQuadraticModel.from_ising({0: 0.0, 1: 0.0}, {(0, 1): -1.0})
        for marker, result_name in (
            ("simAnnSampler = neal.", "simAnnSamples"),
            ("randomSampler = dimod.", "randomSample"),
            ("start = time.time()\nsimAnnSamplesDefault", "simAnnSamplesDefault"),
        ):
            records = []
            for seed in (0, 1):
                np.random.seed(seed)
                namespace = {
                    "np": np, "dimod": dimod, "neal": neal, "time": time,
                    "simAnnSampler": neal.SimulatedAnnealingSampler(),
                    "model_ising": model, "model_random": model,
                }
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(notebook_cell_source(BENCHMARKING_PYTHON_NOTEBOOK_PATH, marker), namespace)
                records.append(namespace[result_name].record)
            with self.subTest(cell=marker):
                np.testing.assert_array_equal(records[0], records[1])

    def test_virtual_best_reuses_the_selected_sweep(self):
        results = self.run_ensemble([1, 2])
        self.assertEqual(results[0]["geometric"]["best"], [0.5, 0.5])
        self.assertEqual(results[1]["geometric"]["best"], [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
