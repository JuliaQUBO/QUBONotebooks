"""Repository policies whose removal would otherwise be silent."""

from __future__ import annotations

import re
import tomllib
import unittest

from notebook_test_support import REPO_ROOT


class RepositoryCommandTests(unittest.TestCase):
    def test_locked_python_environment_excludes_unpatched_diskcache_path(self) -> None:
        # Defect class: an unsafe optional Ocean dependency re-enters either
        # the declared environment or its transitive locked package set.
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text())
        declared = {
            re.match(r"[A-Za-z0-9._-]+", requirement).group(0).lower()
            for requirements in pyproject["dependency-groups"].values()
            for requirement in requirements
        }
        locked = {package["name"].lower() for package in lock["package"]}
        forbidden = {"diskcache", "dwave-ocean-sdk", "dwavebinarycsp"}

        self.assertEqual(set(), declared.intersection(forbidden))
        self.assertEqual(set(), locked.intersection(forbidden))

    def test_qubo_dependency_group_includes_notebook_runtime_packages(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        qubo_packages = {
            re.match(r"[A-Za-z0-9._-]+", requirement).group(0).lower()
            for requirement in pyproject["dependency-groups"]["qubo"]
        }

        self.assertTrue({"dimod", "dwave-neal"}.issubset(qubo_packages))
    def test_colab_installer_default_matches_sysimage_julia_version(self) -> None:
        # Defect class: the installer, deployment workflow, and aggregate
        # notebook manifest silently select different Julia release lines.
        install_script = (REPO_ROOT / "scripts" / "install-colab-julia.sh").read_text()
        deploy_workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text()
        notebook_manifest = tomllib.loads(
            (REPO_ROOT / "notebooks_jl" / "Manifest.toml").read_text()
        )
        installer_match = re.search(r'install-colab-julia "([^"]+)" 2', install_script)
        workflow_match = re.search(r"julia-version:\s*'([^']+)'", deploy_workflow)

        self.assertIsNotNone(installer_match)
        self.assertIsNotNone(workflow_match)
        self.assertEqual(
            {notebook_manifest["julia_version"]},
            {installer_match.group(1), workflow_match.group(1)},
        )

    def test_native_colab_has_a_julia_1_12_manifest(self) -> None:
        manifest_path = (
            REPO_ROOT / "notebooks_jl" / "Manifest-v1.12.toml"
        )
        manifest = tomllib.loads(manifest_path.read_text())
        qci_entry = manifest["deps"]["QCIOpt"][0]

        self.assertEqual("1.12.6", manifest["julia_version"])
        self.assertEqual(
            "30a6074fdd5bd75c3f1cf965329edd01c67e63fe",
            qci_entry["repo-rev"],
        )
        self.assertEqual(
            "https://github.com/SECQUOIA/QCIOpt.jl",
            qci_entry["repo-url"],
        )
    def test_sysimage_includes_julia_qubo_and_gama_runtime_packages(self) -> None:
        # Defect class: a notebook runtime package is omitted from the sysimage,
        # while a richer local depot keeps ordinary verification green.
        create_sysimage = (REPO_ROOT / "scripts" / "create_sysimage.jl").read_text()
        package_lines = {line.strip() for line in create_sysimage.splitlines()}

        expected_packages = {
            '"BinaryWrappers",',
            '"DWave",',
            '"Graphs",',
            '"JuMP",',
            '"Karnak",',
            '"lib4ti2_jll",',
            '"Luxor",',
            '"Measures",',
            '"NPZ",',
            '"Plots",',
            '"PythonCall",',
            '"QiskitOpt",',
            '"QUBO",',
            '"StatsBase",',
            '"StatsPlots",',
        }

        self.assertTrue(
            expected_packages.issubset(package_lines),
            expected_packages - package_lines,
        )
