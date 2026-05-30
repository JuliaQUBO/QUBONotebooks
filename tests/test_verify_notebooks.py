from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_notebooks.py"
SPEC = importlib.util.spec_from_file_location("verify_notebooks", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
verify_notebooks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_notebooks)


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
    def test_default_notebook_is_portable_today(self) -> None:
        self.assertEqual(
            verify_notebooks.DEFAULT_NOTEBOOKS,
            (Path("notebooks_py/2-QUBO_python.ipynb"),),
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
        self.assertIn("verify-notebooks:", makefile)
        self.assertIn("verify-qubo-python:", makefile)
        self.assertIn("./scripts/verify_notebooks.py", makefile)
        self.assertIn("--project=./notebooks_jl", makefile)
        self.assertIn("$(UV) sync --locked", makefile)
        self.assertIn("$(UV) run --locked", makefile)

    def test_sysimage_scripts_use_current_julia_notebook_project(self) -> None:
        create_sysimage = (REPO_ROOT / "scripts" / "create_sysimage.jl").read_text()
        prepare_release = (REPO_ROOT / "scripts" / "prepare_release.jl").read_text()

        self.assertIn('"notebooks_jl"', create_sysimage)
        self.assertIn('"notebooks_jl"', prepare_release)
        self.assertNotIn('"notebooks"', create_sysimage)
        self.assertNotIn('"notebooks"', prepare_release)
