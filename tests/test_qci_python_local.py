"""Credential-free QCi execution and dimensionless model equivalence contracts."""

from __future__ import annotations

import ast
import contextlib
import importlib.util
import io
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO_ROOT / "notebooks_py/6-QCi_python.ipynb"


def code_cells():
    return [
        "".join(cell["source"])
        for cell in json.loads(NOTEBOOK.read_text())["cells"]
        if cell["cell_type"] == "code"
    ]


def cell_containing(marker):
    return next(source for source in code_cells() if marker in source)


def submission_blocks():
    """Keep actual opt-in branches while excluding local model prerequisites."""
    for source in code_cells():
        if "_response = None" not in source or "solve_without_provider_identifiers(" not in source:
            continue
        body = [
            node for node in ast.parse(source).body
            if (isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant) and node.value.value is None)
            or isinstance(node, ast.If)
        ]
        yield compile(ast.Module(body=body, type_ignores=[]), str(NOTEBOOK), "exec")


class QCiCloudBoundaryTests(unittest.TestCase):
    def test_local_make_overrides_command_line_and_inherited_cloud_state(self):
        # Run through a recursive caller: MAKEFLAGS must not restore the opt-in.
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / "uv_probe.py"
            probe.write_text(
                "import json, os, sys\n"
                "print(json.dumps({'flag': os.environ.get('QUBONOTEBOOKS_QCI_ENABLE_CLOUD'), "
                "'token': 'QCI_TOKEN' in os.environ, 'args': sys.argv[1:], "
                "'environment': os.environ.get('UV_PROJECT_ENVIRONMENT')}))\n"
            )
            caller = Path(directory) / "caller.mk"
            caller.write_text(
                f"all:\n\t$(MAKE) -C {shlex.quote(str(REPO_ROOT))} verify-qci-python-local test-qci-python\n"
            )
            result = subprocess.run(
                ["make", "-f", str(caller), "QUBONOTEBOOKS_QCI_ENABLE_CLOUD=1",
                 f"UV={shlex.quote(sys.executable)} {shlex.quote(str(probe))}"],
                cwd=REPO_ROOT,
                env={**os.environ, "QCI_TOKEN": "test-only",
                     "UV_PROJECT_ENVIRONMENT": "/tmp/hostile-shared-env"},
                text=True, capture_output=True, check=True,
            )
        calls = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
        self.assertEqual(2, len(calls))
        for call in calls:
            self.assertEqual("0", call["flag"])
            self.assertFalse(call["token"])
            self.assertEqual(str(REPO_ROOT / "notebooks_py/environments/qci/.venv"), call["environment"])
            self.assertIn("--locked", call["args"])
            self.assertEqual("notebooks_py/environments/qci", call["args"][call["args"].index("--project") + 1])

    def test_default_does_not_read_secrets_or_use_an_inherited_token(self):
        namespace = {"IN_COLAB": True, "os": os}
        with patch.dict(os.environ, {"QCI_TOKEN": "test-only"}, clear=True):
            with contextlib.redirect_stdout(io.StringIO()):
                exec(cell_containing('enable_qci_cloud = os.environ.get'), namespace)
        self.assertFalse(namespace["enable_qci_cloud"])
        self.assertEqual("", namespace["api_token"])

    def test_explicit_opt_in_requires_a_token(self):
        with patch.dict(os.environ, {"QUBONOTEBOOKS_QCI_ENABLE_CLOUD": "1"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "QCI_TOKEN"):
                exec(cell_containing('enable_qci_cloud = os.environ.get'), {"IN_COLAB": False, "os": os})

    def test_disabled_submissions_never_construct_a_client_and_clear_old_results(self):
        blocks = list(submission_blocks())
        self.assertEqual(4, len(blocks))
        # Only the paid-service boundary is doubled; models use real APIs below.
        client = Mock(side_effect=AssertionError("unexpected paid-service access"))
        for block in blocks:
            namespace = {
                "enable_qci_cloud": False, "api_url": "test", "api_token": "test-only",
                "Dirac3ContinuousCloudSolver": client,
                "Dirac3IntegerCloudSolver": client,
                "continuous_response": object(), "binary_response": object(),
                "qubo_response": object(), "constrained_response": object(),
            }
            with contextlib.redirect_stdout(io.StringIO()):
                exec(block, namespace)
            self.assertEqual(1, sum(namespace[key] is None for key in (
                "continuous_response", "binary_response", "qubo_response", "constrained_response"
            )))
        client.assert_not_called()

    def test_enabled_submission_errors_propagate(self):
        for block in submission_blocks():
            client = Mock(side_effect=RuntimeError("provider unavailable"))
            with self.assertRaisesRegex(RuntimeError, "provider unavailable"):
                exec(block, {"enable_qci_cloud": True, "api_url": "test", "api_token": "test-only",
                             "Dirac3ContinuousCloudSolver": client, "Dirac3IntegerCloudSolver": client})
            client.assert_called_once()

    def test_import_notice_filter_is_exact(self):
        source = cell_containing("class OptionalDirectSolverNotice")
        node = next(node for node in ast.parse(source).body
                    if isinstance(node, ast.ClassDef) and node.name == "OptionalDirectSolverNotice")
        namespace = {"logging": logging}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(NOTEBOOK), "exec"), namespace)
        notice_filter = namespace["OptionalDirectSolverNotice"]()
        def record(message="eqc-direct package not available", level=logging.WARNING,
                   path="/venv/eqc_models/solvers/eqcdirect.py", name="root"):
            return logging.LogRecord(name, level, path, 1, message, (), None)
        self.assertFalse(notice_filter.filter(record()))
        for entry in [record(message="another warning"), record(level=logging.ERROR),
                      record(path="/unrelated.py"), record(name="different"),
                      record(message="eqc-direct package not available; more detail")]:
            self.assertTrue(notice_filter.filter(entry))


@unittest.skipUnless(importlib.util.find_spec("eqc_models"), "requires the isolated QCi environment")
class QCiLocalModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.namespace = {}
        with patch.dict(os.environ, {"QUBONOTEBOOKS_QCI_ENABLE_CLOUD": "0", "QCI_TOKEN": "test-only"}):
            with contextlib.redirect_stdout(io.StringIO()):
                for source in code_cells():
                    exec(source, cls.namespace)

    def test_local_models_cover_every_binary_assignment_and_both_optima(self):
        import numpy as np
        ns = self.namespace
        self.assertEqual((2048, 11), ns["local_candidates"].shape)
        self.assertEqual(9, np.count_nonzero(ns["feasible_mask"]))
        self.assertEqual(48, ns["rho"])
        self.assertEqual(144, ns["cQ"])
        self.assertEqual(3, ns["constraint_model"].offset)
        self.assertEqual(5, ns["manual_energies"].min())
        actual = {tuple(row) for row in ns["local_minimizers"]}
        expected = {tuple(1 if j == i else 0 for j in range(11)) for i in (8, 10)}
        self.assertEqual(expected, actual)
        np.testing.assert_allclose(ns["constrained_energies"], ns["manual_energies"])
        np.testing.assert_allclose(ns["continuous_reference"], [20/11, 30/11, 60/11], rtol=1e-6)
        np.testing.assert_allclose(ns["binary_energies"], [0, -0.25, -0.25, 1.5])

    def test_complete_local_cell_order_leaves_cloud_results_absent(self):
        for name in ("continuous_response", "binary_response", "qubo_response", "constrained_response"):
            self.assertIsNone(self.namespace[name])
        self.assertIn("credential_free_checks", self.namespace)
        # The import-only exception must never mute a later real diagnostic.
        self.assertFalse(any(isinstance(f, self.namespace["OptionalDirectSolverNotice"])
                             for f in logging.getLogger().filters))


if __name__ == "__main__":
    unittest.main()
