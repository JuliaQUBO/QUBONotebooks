"""Focused Julia graphs must be selected before the IJulia process starts."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from notebook_test_support import REPO_ROOT, verify_notebooks


FOCUSED = REPO_ROOT / "notebooks_jl/environments/12-Decomposition"
AGGREGATE = REPO_ROOT / "notebooks_jl"
STACK = os.pathsep.join(["@", str(AGGREGATE), "@stdlib"])


class FocusedJuliaLauncherTests(unittest.TestCase):
    def kernel(self, project=None):
        with tempfile.TemporaryDirectory() as directory:
            name, env = verify_notebooks.julia_kernel_spec_dir(
                Path(directory), julia_executable="/owned/julia", project=project,
            )
            spec = json.loads((Path(directory) / "kernels" / name / "kernel.json").read_text())
        return spec, env

    def test_focused_project_and_stack_are_in_effect_before_ijulia_import(self):
        with patch.dict(os.environ, {"JULIA_LOAD_PATH": "inherited-unrelated-project"}):
            spec, env = self.kernel(FOCUSED)
        self.assertEqual(spec["argv"], [
            "/owned/julia", "-i", "--color=yes", f"--project={FOCUSED}",
            "-e", "import IJulia; IJulia.run_kernel()", "{connection_file}",
        ])
        self.assertEqual(spec["env"]["JULIA_LOAD_PATH"], STACK)
        self.assertEqual(env["JULIA_LOAD_PATH"], STACK)
        self.assertEqual(spec["env"]["JULIA_PKG_PRECOMPILE_AUTO"], "0")
        self.assertEqual(spec["env"]["IJULIA_NODEFAULTKERNEL"], "1")

    def test_default_kernel_retains_aggregate_project_and_inherited_stack(self):
        spec, env = self.kernel()
        self.assertIn(f"--project={AGGREGATE}", spec["argv"])
        self.assertNotIn("JULIA_LOAD_PATH", spec["env"])
        self.assertNotIn("JULIA_LOAD_PATH", env)

    def test_selected_cli_project_reaches_instantiation_and_kernel_environment(self):
        args = ["verify_notebooks.py", "--julia-project", str(FOCUSED.relative_to(REPO_ROOT)),
                "notebooks_jl/12-Decomposition.ipynb"]
        with patch.object(sys, "argv", args), patch.object(verify_notebooks, "run") as run:
            self.assertEqual(verify_notebooks.main(), 0)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0][1], f"--project={AGGREGATE}")
        self.assertEqual(commands[1][1], f"--project={FOCUSED}")
        self.assertEqual(run.call_args_list[1].kwargs["env"]["JULIA_LOAD_PATH"], STACK)
        self.assertEqual(run.call_args_list[2].kwargs["env"]["JULIA_LOAD_PATH"], STACK)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"]["IJULIA_NODEFAULTKERNEL"], "1")
        self.assertIn("--ExecutePreprocessor.kernel_name=qubonotebooks-julia-local", commands[2])

    def test_default_cli_still_has_one_aggregate_instantiation(self):
        with patch.object(sys, "argv", ["verify_notebooks.py", "notebooks_jl/7-CanonicalProblems.ipynb"]), \
                patch.object(verify_notebooks, "run") as run:
            self.assertEqual(verify_notebooks.main(), 0)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].args[0][1], "--project=./notebooks_jl")
        for call in run.call_args_list:
            self.assertNotIn("JULIA_LOAD_PATH", call.kwargs["env"])

    def test_invalid_selected_project_fails_before_launch(self):
        with patch.object(sys, "argv", ["verify_notebooks.py", "--julia-project", "/missing/project",
                                        "notebooks_jl/12-Decomposition.ipynb"]), \
                patch.object(verify_notebooks, "run") as run:
            with self.assertRaisesRegex(FileNotFoundError, "Julia project was not found"):
                verify_notebooks.main()
        run.assert_not_called()

    def test_python_only_run_rejects_ignored_julia_project(self):
        with patch.object(sys, "argv", ["verify_notebooks.py", "--julia-project", str(FOCUSED)]), \
                patch.object(verify_notebooks, "run") as run:
            with self.assertRaisesRegex(ValueError, "requires a Julia notebook"):
                verify_notebooks.main()
        run.assert_not_called()


class DecompositionMakeStartupTests(unittest.TestCase):
    def commands(self, target):
        result = subprocess.run(["make", "--dry-run", target], cwd=REPO_ROOT,
                                capture_output=True, text=True, check=True)
        return [shlex.split(line) for line in result.stdout.splitlines()]

    def test_preparation_selects_focused_graph_before_loading_kernel_tools(self):
        commands = self.commands("prepare-decomposition-julia")
        instantiations = [c for c in commands if any(s.startswith("--project=") for s in c)]
        self.assertEqual(len(instantiations), 2)
        self.assertIn("--project=notebooks_jl", instantiations[0])
        self.assertNotIn("IJulia", instantiations[0][-1])
        self.assertIn(f"--project={FOCUSED.relative_to(REPO_ROOT)}", instantiations[1])
        self.assertIn(f"JULIA_LOAD_PATH={STACK}", instantiations[1])
        self.assertIn("using IJulia", instantiations[1][-1])
        for command in instantiations:
            self.assertIn("IJULIA_NODEFAULTKERNEL=1", command)
            self.assertIn("JULIA_NUM_PRECOMPILE_TASKS=1", command)

    def test_only_decomposition_target_selects_focused_verifier_project(self):
        for target, expected in (("verify-decomposition-julia-local", True),
                                 ("verify-canonical-problems-julia", False)):
            with self.subTest(target=target):
                commands = self.commands(target)
                run = next(c for c in commands if "./scripts/verify_notebooks.py" in c)
                self.assertEqual("--julia-project" in run, expected)
                if expected:
                    self.assertEqual(run[run.index("--julia-project") + 1], str(FOCUSED.relative_to(REPO_ROOT)))
                    recursive = next(c for c in commands if "QUBONOTEBOOKS_NOTEBOOK_TIMEOUT=180" in c)
                    self.assertIn("IJULIA_NODEFAULTKERNEL=1", recursive)


if __name__ == "__main__":
    unittest.main()
