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
QUBO_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "2-QUBO.ipynb"
QUBO_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "2-QUBO_python.ipynb"
GAMA_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "3-GAMA.ipynb"
GAMA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "3-GAMA_python.ipynb"
DWAVE_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "4-DWave.ipynb"
DWAVE_PYTHON_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "4-DWAVE_python.ipynb"
JULIA_COLAB_NOTEBOOK_PATHS = (
    REPO_ROOT / "notebooks_jl" / "1-MathProg.ipynb",
    REPO_ROOT / "notebooks_jl" / "2-QUBO.ipynb",
    REPO_ROOT / "notebooks_jl" / "3-GAMA.ipynb",
    REPO_ROOT / "notebooks_jl" / "4-DWave.ipynb",
    REPO_ROOT / "notebooks_jl" / "5-Benchmarking.ipynb",
)
COLAB_JULIA_INSTALLER = (
    'bash <(curl -s "https://raw.githubusercontent.com/JuliaQUBO/QUBONotebooks/main/'
    'scripts/install-colab-julia.sh")'
)
NOTEBOOK_DIRS = (
    REPO_ROOT / "notebooks_jl",
    REPO_ROOT / "notebooks_py",
)
GAMA_DATA_FILES = (
    REPO_ROOT / "notebooks_data" / "3-GAMA_example4_coefficients.csv",
    REPO_ROOT / "notebooks_data" / "3-GAMA_example4_feasible_starts.csv",
)
SPEC = importlib.util.spec_from_file_location("verify_notebooks", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
verify_notebooks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_notebooks)


def notebook_source(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def notebook_cell_source(path: Path, marker: str) -> str:
    notebook = json.loads(path.read_text())

    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if marker in source:
            return source

    raise AssertionError(f"Could not find notebook cell containing {marker!r}")


def notebook_cell_sources(path: Path) -> list[str]:
    notebook = json.loads(path.read_text())
    return ["".join(cell.get("source", [])) for cell in notebook["cells"]]


def notebook_paths() -> list[Path]:
    return sorted(path for directory in NOTEBOOK_DIRS for path in directory.glob("*.ipynb"))


class NotebookSourceSafetyTests(unittest.TestCase):
    def test_notebooks_do_not_use_jump_unsafe_backend(self) -> None:
        offenders = [
            path.relative_to(REPO_ROOT).as_posix()
            for path in notebook_paths()
            if "unsafe_backend" in notebook_source(path)
        ]

        self.assertEqual([], offenders)


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
        self.assertIn("verify-python-portable:", makefile)
        self.assertIn("verify-qubo-python:", makefile)
        self.assertIn("verify-gama-python:", makefile)
        self.assertIn("verify-benchmarking-python:", makefile)
        self.assertIn("PORTABLE_PYTHON_NOTEBOOKS", makefile)
        self.assertIn("./scripts/verify_notebooks.py", makefile)
        self.assertIn("--project=./notebooks_jl", makefile)
        self.assertIn("$(UV) sync --locked", makefile)
        self.assertIn("$(UV) run --locked", makefile)

    def test_locked_python_environment_excludes_unpatched_diskcache_path(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        lock = (REPO_ROOT / "uv.lock").read_text()

        self.assertNotIn("dwave-ocean-sdk", pyproject)
        self.assertNotIn("dwave-ocean-sdk", lock)
        self.assertNotIn('name = "diskcache"', lock)
        self.assertIn("GHSA-w8v5-vhqr-4h9v", (REPO_ROOT / "README.md").read_text())

    def test_qubo_dependency_group_includes_notebook_runtime_packages(self) -> None:
        pyproject = (REPO_ROOT / "pyproject.toml").read_text()
        qubo_group = pyproject[
            pyproject.index("qubo = [") : pyproject.index("\n]\n\n[tool.uv]")
        ]

        self.assertIn('"dimod>=0.12,<1"', qubo_group)
        self.assertIn('"dwave-neal>=0.6,<1"', qubo_group)

    def test_sysimage_scripts_use_current_julia_notebook_project(self) -> None:
        create_sysimage = (REPO_ROOT / "scripts" / "create_sysimage.jl").read_text()
        prepare_release = (REPO_ROOT / "scripts" / "prepare_release.jl").read_text()

        self.assertIn('"notebooks_jl"', create_sysimage)
        self.assertIn('"notebooks_jl"', prepare_release)
        self.assertNotIn('"notebooks"', create_sysimage)
        self.assertNotIn('"notebooks"', prepare_release)

    def test_colab_installer_default_matches_sysimage_julia_version(self) -> None:
        install_script = (REPO_ROOT / "scripts" / "install-colab-julia.sh").read_text()
        deploy_workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text()
        notebook_manifest = (REPO_ROOT / "notebooks_jl" / "Manifest.toml").read_text()
        expected_version = "1.10.11"

        self.assertIn(f'install-colab-julia "{expected_version}" 2', install_script)
        self.assertIn(f"julia-version: '{expected_version}'", deploy_workflow)
        self.assertIn(f'julia_version = "{expected_version}"', notebook_manifest)

    def test_sysimage_build_and_colab_kernel_use_matching_depot_path(self) -> None:
        install_script = (REPO_ROOT / "scripts" / "install-colab-julia.sh").read_text()
        deploy_workflow = (REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text()
        release_notes = (REPO_ROOT / ".github" / "workflows" / "NOTES.md").read_text()

        self.assertIn(
            "JULIA_DEPOT_PATH: /content/.julia-depot:/home/runner/.julia",
            deploy_workflow,
        )
        self.assertIn("sudo mkdir -p /content/.julia-depot", deploy_workflow)
        self.assertIn('COLAB_JULIA_DEPOT="/content/.julia-depot"', install_script)
        self.assertIn('export JULIA_DEPOT_PATH="$COLAB_JULIA_DEPOT:', install_script)
        self.assertIn('"JULIA_DEPOT_PATH"=>ENV["JULIA_DEPOT_PATH"]', install_script)
        self.assertIn("tar -xzf sysimage.tar.gz -C /content", release_notes)
        self.assertIn('export JULIA_DEPOT_PATH="/content/.julia-depot:', release_notes)

    def test_sysimage_includes_julia_qubo_and_gama_runtime_packages(self) -> None:
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
            '"QUBO",',
            '"StatsBase",',
            '"StatsPlots",',
        }

        self.assertTrue(
            expected_packages.issubset(package_lines),
            expected_packages - package_lines,
        )


class JuliaColabSetupTests(unittest.TestCase):
    def test_all_julia_notebooks_install_colab_julia_before_activation(self) -> None:
        for path in JULIA_COLAB_NOTEBOOK_PATHS:
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cell_sources(path)
                install_indexes = [
                    i for i, source in enumerate(cells) if COLAB_JULIA_INSTALLER in source
                ]
                activate_indexes = [
                    i for i, source in enumerate(cells) if "Pkg.activate(@__DIR__)" in source
                ]

                self.assertEqual([2], install_indexes)
                self.assertTrue(activate_indexes)
                self.assertLess(install_indexes[0], min(activate_indexes))
                self.assertIn("precompiled QUBONotebooks sysimage", cells[install_indexes[0] - 1])


class PythonNotebookDependencySetupTests(unittest.TestCase):
    def test_qubo_colab_install_includes_scipy_before_imports(self) -> None:
        cells = notebook_cell_sources(QUBO_NOTEBOOK_PATH)
        install_cell = notebook_cell_source(QUBO_NOTEBOOK_PATH, "!pip install -q pyomo")
        import_cell = notebook_cell_source(QUBO_NOTEBOOK_PATH, "from scipy.special import gamma")

        self.assertIn("!pip install dimod scipy", install_cell)
        self.assertLess(cells.index(install_cell), cells.index(import_cell))

    def test_gama_installs_missing_dimod_and_neal_outside_colab(self) -> None:
        install_cell = notebook_cell_source(GAMA_NOTEBOOK_PATH, "subprocess.check_call")

        self.assertIn("try:\n    import dimod\n    import neal", install_cell)
        self.assertIn(
            '[sys.executable, "-m", "pip", "install", "dimod", "dwave-neal"]',
            install_cell,
        )
        self.assertNotIn("if IN_COLAB", install_cell)


class GamaNotebookTests(unittest.TestCase):
    def test_gama_notebook_has_portable_py4ti2_fallback(self) -> None:
        source = notebook_source(GAMA_NOTEBOOK_PATH)

        self.assertIn("HAS_PY4TI2", source)
        self.assertIn("load_precomputed_graver_basis", source)
        self.assertIn("notebooks_py/graver.npy", source)
        self.assertIn("3-GAMA_example4_feasible_starts.csv", source)
        self.assertIn("np.random.default_rng(271828)", source)

        for path in GAMA_DATA_FILES:
            self.assertTrue(path.is_file(), f"{path} should be committed")

    def test_gama_notebook_source_outputs_are_cleared(self) -> None:
        notebook = json.loads(GAMA_NOTEBOOK_PATH.read_text())

        for cell in notebook["cells"]:
            if cell.get("cell_type") == "code":
                self.assertIsNone(cell.get("execution_count"))
                self.assertEqual(cell.get("outputs", []), [])


class DWaveNotebookTests(unittest.TestCase):
    def test_julia_topology_section_uses_current_sampler_topology(self) -> None:
        source = notebook_source(DWAVE_JULIA_NOTEBOOK_PATH)

        self.assertIn('solver=Dict("qpu" => true)', source)
        self.assertIn('set_optimizer_attribute(qubo_model, "return_embedding", true)', source)
        self.assertIn("DWave.WorkingGraph(sampler)", source)
        self.assertIn("DWave.WorkingGraph(QUBOTools.metadata(sampleset))", source)
        self.assertIn("DWave.embedding(sampleset)", source)
        self.assertIn("DWave.draw_topology(arch", source)
        self.assertIn("DWave.draw_embedding(sampleset", source)
        self.assertIn('DWave.PythonCall.pyimport("matplotlib")', source)
        self.assertLess(
            source.index('DWave.PythonCall.pyimport("matplotlib")'),
            source.index("using Plots"),
        )
        self.assertIn('if !haskey(ENV, "DWAVE_API_TOKEN")', source)
        self.assertIn("QUBOTools.solution(QUBOTools.backend(qubo_model))", source)
        self.assertIn('repo-rev = "v0.7.6"', (REPO_ROOT / "notebooks_jl" / "Manifest.toml").read_text())
        self.assertNotIn("networkx_edges", source)
        self.assertNotIn("graph_from_edges", source)
        self.assertNotIn("graph_layout_subset", source)
        self.assertNotIn("sampler.to_networkx_graph()", source)
        self.assertNotIn("import PythonCall: pyconvert, pyimport", source)
        self.assertNotIn("using GraphPlot", source)
        self.assertNotIn("gplot(", source)
        self.assertNotIn("Graphs.grpah", source)
        self.assertNotIn("DW_2000Q_6", source)
        self.assertNotIn("Advantage_system1.1", source)
        self.assertNotIn("Advantage_system4.1", source)
        self.assertNotIn("DWave.dwave_networkx.chimera_graph", source)
        self.assertNotIn("DWave.dwave_networkx.pegasus_graph", source)
        self.assertNotIn('ENV["DWAVE_API_TOKEN"] = "<YOUR_KEY_HERE>";', source)
        self.assertNotIn("QUBOTools.sampleset", source)

    def test_python_topology_section_uses_current_sampler_topology(self) -> None:
        source = notebook_source(DWAVE_PYTHON_NOTEBOOK_PATH)

        self.assertIn('DWaveSampler(solver={"qpu": True})', source)
        self.assertIn('qpu.properties["topology"]', source)
        self.assertIn("qpu.to_networkx_graph()", source)
        self.assertIn("EmbeddingComposite(qpu)", source)
        self.assertIn('topology_type == "chimera"', source)
        self.assertIn('topology_type == "pegasus"', source)
        self.assertIn('topology_type == "zephyr"', source)
        self.assertNotIn('qpu.solver.id == "DW_2000Q_6"', source)
        self.assertNotIn("dnx.chimera_graph", source)
        self.assertNotIn("dnx.pegasus_graph", source)

    def test_julia_embedding_plot_overlays_embedding_on_full_topology(self) -> None:
        source = notebook_cell_source(DWAVE_JULIA_NOTEBOOK_PATH, "function draw_embedding")

        self.assertIn("DWave.embedding(sampleset)", source)
        self.assertIn("DWave.WorkingGraph(QUBOTools.metadata(sampleset))", source)
        self.assertIn("DWave.draw_embedding(sampleset; node_size=2)", source)
        self.assertIn("$(length(arch.nodes))-qubit working graph", source)
        self.assertNotIn("graph_layout_subset", source)
        self.assertNotIn("nodefillc = fill", source)
        self.assertNotIn("gplot(", source)

    def test_julia_quantum_annealer_output_analysis_matches_python_views(self) -> None:
        julia_source = notebook_cell_source(DWAVE_JULIA_NOTEBOOK_PATH, "qpu_solution = QUBOTools.solution")
        python_source = notebook_cell_source(DWAVE_PYTHON_NOTEBOOK_PATH, "plot_enumerate(DWaveSamples")

        self.assertIn("QUBOTools.solution(QUBOTools.backend(qubo_model))", julia_source)
        self.assertIn("QUBOTools.EnergyDistributionPlot(qpu_solution)", julia_source)
        self.assertIn("QUBOTools.EnergyFrequencyPlot(qpu_solution)", julia_source)
        self.assertIn("display(plot(QUBOTools.EnergyDistributionPlot", julia_source)
        self.assertLess(
            julia_source.index("QUBOTools.EnergyDistributionPlot(qpu_solution)"),
            julia_source.index("QUBOTools.EnergyFrequencyPlot(qpu_solution)"),
        )
        self.assertIn("plot_enumerate(DWaveSamples", python_source)
        self.assertIn("plot_energies(DWaveSamples", python_source)

    def test_live_dwave_outputs_are_refreshed_without_duplicate_julia_plot_formats(self) -> None:
        julia_notebook = json.loads(DWAVE_JULIA_NOTEBOOK_PATH.read_text())
        python_notebook = json.loads(DWAVE_PYTHON_NOTEBOOK_PATH.read_text())

        julia_markers = (
            "DWave.dwave_system.DWaveSampler",
            "qpu_solution = QUBOTools.solution",
            "function draw_topology",
            "function draw_embedding",
        )
        python_markers = (
            'qpu = DWaveSampler(solver={"qpu": True})',
            "EmbeddingComposite(qpu)",
        )

        julia_cells = [
            cell
            for cell in julia_notebook["cells"]
            if any(marker in "".join(cell.get("source", [])) for marker in julia_markers)
        ]
        python_cells = [
            cell
            for cell in python_notebook["cells"]
            if any(marker in "".join(cell.get("source", [])) for marker in python_markers)
        ]

        self.assertEqual(len(julia_cells), len(julia_markers))
        self.assertEqual(len(python_cells), len(python_markers))

        for cell in julia_cells + python_cells:
            self.assertIsNotNone(cell.get("execution_count"))

        analysis_image_outputs = [
            output
            for output in julia_cells[1].get("outputs", [])
            if "image/png" in output.get("data", {})
        ]
        self.assertGreaterEqual(len(analysis_image_outputs), 2)
        self.assertTrue(julia_cells[2].get("outputs"))
        self.assertTrue(julia_cells[3].get("outputs"))
        self.assertTrue(python_cells[0].get("outputs"))

        for cell in julia_notebook["cells"]:
            for output in cell.get("outputs", []):
                data = output.get("data", {})
                if "image/png" in data:
                    self.assertEqual(set(data), {"image/png"})
