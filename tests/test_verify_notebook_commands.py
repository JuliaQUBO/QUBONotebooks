"""Behavioral tests for the notebook verifier CLI helpers."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from notebook_test_support import REPO_ROOT, verify_notebooks


class CudaqTargetTests(unittest.TestCase):
    def commands(self, target, *overrides):
        result = subprocess.run(
            ["make", "--dry-run", target, *overrides], cwd=REPO_ROOT,
            env={**os.environ, "QUBONOTEBOOKS_DWAVE_ENABLE_QPU": "1",
                 "CUDA_VISIBLE_DEVICES": "0", "DWAVE_API_TOKEN": "test-token"},
            capture_output=True, text=True, check=True,
        )
        return [shlex.split(line) for line in result.stdout.splitlines()]

    def test_cudaq_target_installs_optional_group_and_forces_local_execution(self):
        commands = self.commands("verify-cudaq-python")
        sync = next(command for command in commands if "sync" in command)
        run = next(command for command in commands if "./scripts/verify_cudaq.py" in command)
        for command in (sync, run):
            self.assertIn("--locked", command)
            groups = [command[i + 1] for i, token in enumerate(command) if token == "--group"]
            self.assertEqual(["docs", "qubo", "cudaq"], groups)
        self.assertIn("QUBONOTEBOOKS_DWAVE_ENABLE_QPU=0", run)
        self.assertIn("CUDA_VISIBLE_DEVICES=", run)
        self.assertIn("PYTHONWARNINGS=error", run)
        self.assertEqual(["env", "-u", "DWAVE_API_TOKEN"], run[:3])
        self.assertEqual("notebooks_py/4-DWAVE_python.ipynb", run[-1])

    def test_cudaq_target_accepts_the_notebook_list_for_future_sections(self):
        commands = self.commands(
            "verify-cudaq-python",
            "CUDAQ_PYTHON_NOTEBOOKS=notebooks_py/2-QUBO_python.ipynb notebooks_py/4-DWAVE_python.ipynb",
        )
        run = next(command for command in commands if "./scripts/verify_cudaq.py" in command)
        self.assertEqual(["notebooks_py/2-QUBO_python.ipynb", "notebooks_py/4-DWAVE_python.ipynb"], run[-2:])

    def test_portable_target_still_uses_only_docs_and_qubo(self):
        commands = self.commands("verify-python-portable")
        run = next(command for command in commands if "./scripts/verify_notebooks.py" in command)
        groups = [run[i + 1] for i, token in enumerate(run) if token == "--group"]
        self.assertEqual(["docs", "qubo"], groups)
        self.assertEqual(["notebooks_py/2-QUBO_python.ipynb", "notebooks_py/3-GAMA_python.ipynb"], run[-2:])


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
        self.assertIn(str(REPO_ROOT / "scripts/start_python_kernel.py"), kernel["argv"])
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
    @unittest.skipIf(sys.platform == "win32", "Windows retains the default Jupyter transport")
    def test_python_kernel_uses_private_local_ipc(self) -> None:
        """Execute through the real runner and inspect the kernel's active transport."""
        with tempfile.TemporaryDirectory() as tmp_name:
            tmp = Path(tmp_name)
            kernel_name, env = verify_notebooks.python_kernel_spec_dir(tmp)
            notebook = tmp / "transport.ipynb"
            env["PYTHONWARNINGS"] = "error"
            notebook.write_text(json.dumps({
                "nbformat": 4, "nbformat_minor": 5, "metadata": {},
                "cells": [{
                    "id": "transport-check", "cell_type": "code", "metadata": {},
                    "execution_count": None, "outputs": [],
                    "source": [
                        "from IPython import get_ipython\n",
                        "from pathlib import Path\n",
                        "app = get_ipython().kernel.parent\n",
                        "private = Path(app.ip).parent.stat().st_mode & 0o077 == 0\n",
                        "print(app.transport, private)\n",
                    ],
                }],
            }))
            # Capture the real subprocess, including startup/shutdown diagnostics
            # that Jupyter does not store in the executed notebook's outputs.
            real_run = subprocess.run
            transcript = tmp / "kernel.log"
            with transcript.open("w") as log:
                def capture_run(*args, **kwargs):
                    return real_run(*args, **kwargs, stdout=log, stderr=subprocess.STDOUT)

                with patch.object(verify_notebooks, "REPO_ROOT", tmp):
                    with patch.object(subprocess, "run", side_effect=capture_run):
                        verify_notebooks.execute_notebook(
                            notebook, timeout_seconds=30, kernel_name=kernel_name, env=env,
                        )
            log_text = transcript.read_text()
            self.assertIn("Writing", log_text)
            self.assertNotRegex(log_text, r"WARNING|ERROR|\w+Warning:")
            executed = json.loads((tmp / ".nbverify" / notebook.name).read_text())
            output = "".join(
                "".join(item.get("text", [])) for item in executed["cells"][0]["outputs"]
            )
        self.assertEqual("ipc True\n", output)

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

        self.assertEqual(cmd[1:3], ["-m", "nbconvert"])
        self.assertIn("--execute", cmd)
        self.assertIn("--ExecutePreprocessor.timeout=42", cmd)
        self.assertIn("--ExecutePreprocessor.kernel_name=test-kernel", cmd)
        self.assertEqual(cmd[-1], "notebooks_py/1-MathProg_python.ipynb")
        self.assertEqual(env, {"JUPYTER_PATH": "/tmp/kernels"})
