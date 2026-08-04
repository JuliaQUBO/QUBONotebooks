"""Derived notebook setup and dependency contracts."""

from __future__ import annotations

import json
import re
import tomllib
import unittest

from notebook_test_support import (
    JULIA_COLAB_NOTEBOOK_PATHS,
    REPO_ROOT,
    notebook_cell_sources,
    notebook_source,
)


class JuliaColabSetupTests(unittest.TestCase):
    def test_all_julia_notebooks_use_native_colab_julia_bootstrap(self) -> None:
        # Defect class: one notebook bypasses the shared bootstrap or activates
        # its environment before the native Colab runtime is initialized.
        for path in JULIA_COLAB_NOTEBOOK_PATHS:
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cell_sources(path)
                setup_indexes = [
                    i
                    for i, source in enumerate(cells)
                    if (
                        "Base.invokelatest(QUBONotebooksBootstrap.bootstrap_notebook"
                        in source
                    )
                ]
                activate_indexes = [
                    i
                    for i, source in enumerate(cells)
                    if "Pkg.activate(JULIA_PROJECT_DIR" in source
                ]
                expected_call = (
                    "Base.invokelatest("
                    f'QUBONotebooksBootstrap.bootstrap_notebook, "{path.stem}")'
                )
                metadata = json.loads(path.read_text())["metadata"]["kernelspec"]

                self.assertEqual(1, len(setup_indexes))
                self.assertIn(expected_call, cells[setup_indexes[0]])
                self.assertTrue(activate_indexes)
                self.assertIn(
                    "Pkg.activate(JULIA_PROJECT_DIR; io = devnull)",
                    cells[activate_indexes[0]],
                )
                self.assertIn(
                    "Pkg.activate(@__DIR__; io = devnull)",
                    cells[activate_indexes[0]],
                )
                self.assertLess(setup_indexes[0], min(activate_indexes))
                self.assertNotIn("%%shell", notebook_source(path))
                self.assertNotIn("install-colab-julia.sh", notebook_source(path))
                self.assertEqual(
                    {"display_name": "Julia", "language": "julia", "name": "julia"},
                    metadata,
                )


class PythonNotebookDependencySetupTests(unittest.TestCase):
    def test_benchmarking_installs_progress_dependency(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        qubo_packages = {
            re.match(r"[A-Za-z0-9._-]+", requirement).group(0).lower()
            for requirement in pyproject["dependency-groups"]["qubo"]
        }

        self.assertTrue("tqdm" in qubo_packages)
