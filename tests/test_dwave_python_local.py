"""The local D-Wave lane must not discover or contact a saved QPU account."""

import builtins
import contextlib
import io
import json
import os
import subprocess
import unittest
from unittest.mock import Mock, patch

from makefile_support import command_with_assignment
from notebook_test_support import REPO_ROOT


def cell_containing(marker):
    notebook = json.loads(
        (REPO_ROOT / "notebooks_py/4-DWAVE_python.ipynb").read_text()
    )
    return next(
        "".join(cell["source"]) for cell in notebook["cells"]
        if cell["cell_type"] == "code" and marker in "".join(cell["source"])
    )


class DWaveLocalTests(unittest.TestCase):
    def test_default_does_not_read_colab_secrets_or_use_inherited_token(self):
        namespace = {"IN_COLAB": True}
        with patch.dict(os.environ, {"DWAVE_API_TOKEN": "test-token"}, clear=True):
            with contextlib.redirect_stdout(io.StringIO()):
                exec(cell_containing('api_token = ""'), namespace)
        self.assertFalse(namespace["enable_qpu"])
        self.assertEqual("", namespace["api_token"])

    def test_ping_requires_opt_in_and_propagates_failure(self):
        source = cell_containing('subprocess.run(["dwave", "ping"]')
        with patch("subprocess.run") as ping, contextlib.redirect_stdout(io.StringIO()):
            exec(source, {"enable_qpu": False})
            ping.assert_not_called()
            ping.side_effect = subprocess.CalledProcessError(1, ["dwave", "ping"])
            with self.assertRaises(subprocess.CalledProcessError):
                exec(source, {"enable_qpu": True})
            ping.assert_called_once_with(["dwave", "ping"], check=True)

    def test_disabled_qpu_does_not_load_ocean(self):
        original_import = builtins.__import__
        attempted = []

        def reject_ocean(name, *args, **kwargs):
            if name.startswith("dwave.system"):
                attempted.append(name)
                raise ModuleNotFoundError(name)
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_ocean):
            exec(cell_containing("from dwave.system import"), {"enable_qpu": False})
        self.assertEqual([], attempted)

    def test_disabled_qpu_never_constructs_client_even_with_credentials(self):
        for token in ("", "test-token"):
            with self.subTest(token_present=bool(token)):
                sampler = Mock(side_effect=RuntimeError("unexpected QPU access"))
                namespace = {"enable_qpu": False, "api_token": token,
                             "DWaveSampler": sampler}
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(cell_containing("qpu = DWaveSampler(token="), namespace)
                sampler.assert_not_called()
                self.assertFalse(namespace["qpu_available"])

    def test_enabled_client_failure_is_not_reported_as_local_success(self):
        namespace = {"enable_qpu": True, "api_token": "test-token",
                     "DWaveSampler": Mock(side_effect=RuntimeError("connection failed"))}
        with self.assertRaisesRegex(RuntimeError, "connection failed"):
            exec(cell_containing("qpu = DWaveSampler(token="), namespace)

    def test_local_target_overrides_inherited_opt_in(self):
        result = subprocess.run(
            ["make", "--dry-run", "verify-dwave-python-local"], cwd=REPO_ROOT,
            env={**os.environ, "QUBONOTEBOOKS_DWAVE_ENABLE_QPU": "1",
                 "DWAVE_API_TOKEN": "test-token"},
            text=True, capture_output=True, check=True,
        )
        command = command_with_assignment(result.stdout, "QUBONOTEBOOKS_DWAVE_ENABLE_QPU")
        self.assertIn("QUBONOTEBOOKS_DWAVE_ENABLE_QPU=0", command)
        self.assertIn("-u", command)
        self.assertIn("DWAVE_API_TOKEN", command)
        self.assertIn("NOTEBOOKS=notebooks_py/4-DWAVE_python.ipynb", command)
        self.assertIn("UV_GROUP_FLAGS=--group docs --group qubo", command)
