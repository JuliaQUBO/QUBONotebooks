from __future__ import annotations

import itertools
import json
import re
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "6-QCi.ipynb"
QCI_REVISION = "30a6074fdd5bd75c3f1cf965329edd01c67e63fe"


def notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text())


def notebook_source() -> str:
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook()["cells"]
    )


def notebook_cell(data: dict, cell_id: str) -> dict:
    matches = [cell for cell in data["cells"] if cell.get("id") == cell_id]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected one cell with id {cell_id!r}, found {len(matches)}"
        )
    return matches[0]


def cell_output_text(cell: dict) -> str:
    parts = []
    for output in cell.get("outputs", []):
        value = output.get("text", output.get("data", {}).get("text/plain", ""))
        parts.append("".join(value) if isinstance(value, list) else value)
    return "\n".join(parts)


def small_qubo_energy(bits: tuple[int, ...]) -> int:
    return (sum(bits) - 1) ** 2


class QCIJuliaNotebookTests(unittest.TestCase):
    def test_notebook_has_tutorial_structure_and_feature_map(self) -> None:
        source = notebook_source()
        required_markers = (
            "## Setup",
            "## Learning objectives",
            "## Prerequisites",
            "## A small QUBO with an independent exact check",
            "## QCIOpt attributes and optional cloud execution",
            "## Python-to-Julia feature map",
            "## Practice checkpoints",
            "## Summary",
            "## References",
            "Continuous constrained Dirac-3",
            "QUBO through DIRAC-1",
            "manual penalty reformulation",
            "Python-only",
            "https://github.com/SECQUOIA/QCIOpt.jl",
            "not officially supported by Quantum Computing Inc.",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

    def test_default_path_builds_model_and_checks_exact_qubo_offline(self) -> None:
        data = notebook()
        model_source = "".join(notebook_cell(data, "qubo-model")["source"])
        exact_source = "".join(notebook_cell(data, "exact-check")["source"])
        live_source = "".join(notebook_cell(data, "qci-live")["source"])

        self.assertIn("Model(QCIOpt.Optimizer)", model_source)
        self.assertIn("@variable(qci_model, x[1:3], Bin)", model_source)
        self.assertIn("@objective(qci_model, Min, (sum(x) - 1)^2)", model_source)
        self.assertIn("all_binary_states(3)", exact_source)
        self.assertIn(
            "small_qubo_energy(bits) = (sum(bits) - 1)^2",
            exact_source,
        )
        self.assertIn("exact_best_energy == 0", exact_source)
        self.assertNotIn("optimize!", model_source)
        self.assertNotIn("optimize!", exact_source)
        self.assertIn("optimize!(qci_model)", live_source)

        states = list(itertools.product((0, 1), repeat=3))
        optimum = min(small_qubo_energy(bits) for bits in states)
        optima = {bits for bits in states if small_qubo_energy(bits) == optimum}

        self.assertEqual(0, optimum)
        self.assertEqual({(1, 0, 0), (0, 1, 0), (0, 0, 1)}, optima)

    def test_live_path_is_explicit_fail_closed_and_validates_results(self) -> None:
        data = notebook()
        attribute_source = "".join(
            notebook_cell(data, "attribute-config")["source"]
        )
        guard_source = "".join(notebook_cell(data, "qci-guard")["source"])
        live_source = "".join(notebook_cell(data, "qci-live")["source"])
        solution_attribute_source = "".join(
            notebook_cell(data, "solution-attributes")["source"]
        )
        full_source = notebook_source()

        required_guard_markers = (
            'get(ENV, "QUBONOTEBOOKS_QCI_ENABLE_CLOUD", "0") == "1"',
            "QUBONOTEBOOKS_QCI_REQUIRE_CLOUD",
            'get(ENV, "QCI_TOKEN", "")',
            "require_qci_credentials()",
            "isempty(strip(token)) && error(",
        )
        for marker in required_guard_markers:
            self.assertIn(marker, guard_source)

        required_attribute_markers = (
            "QCIOpt.DeviceType()",
            'MOI.RawOptimizerAttribute("num_samples")',
            "get_attribute(qci_model, QCIOpt.DeviceType())",
        )
        for marker in required_attribute_markers:
            self.assertIn(marker, attribute_source)
        self.assertIn(
            "qci_status_after_attribute_config = "
            "termination_status(qci_model)",
            attribute_source,
        )
        self.assertIn(
            "@assert qci_status_after_attribute_config == "
            "MOI.OPTIMIZE_NOT_CALLED",
            solution_attribute_source,
        )
        self.assertNotIn(
            "@assert termination_status(qci_model) == "
            "MOI.OPTIMIZE_NOT_CALLED",
            solution_attribute_source,
        )

        required_live_markers = (
            'MOI.RawOptimizerAttribute("api_token")',
            "result_count(qci_model)",
            "value.(x; result=result_index)",
            "objective_value(qci_model; result=result_index)",
            "QCIOpt.ResultMultiplicity(result_index)",
            "small_qubo_energy(bits)",
            "isapprox(recomputed_energy, reported_energy",
            "qci_cloud_submitted",
        )
        for marker in required_live_markers:
            self.assertIn(marker, live_source)

        self.assertLess(
            live_source.index("require_qci_credentials()"),
            live_source.index("optimize!(qci_model)"),
        )
        self.assertNotIn("NumberOfReads()", live_source)
        self.assertNotIn("job_id", live_source.lower())
        self.assertNotIn("account", live_source.lower())
        self.assertNotRegex(
            full_source,
            re.compile(r'(?i)QCI_TOKEN\s*=\s*["\'][^"\']+["\']'),
        )

    def test_live_result_validation_rejects_fractional_values_before_rounding(
        self,
    ) -> None:
        data = notebook()
        exact_source = "".join(notebook_cell(data, "exact-check")["source"])
        live_source = "".join(notebook_cell(data, "qci-live")["source"])

        self.assertIn(
            "validated_binary_bits(raw_values; atol = 1e-8)",
            exact_source,
        )
        self.assertIn("rtol = 0.0", exact_source)
        self.assertIn("[0.4, 0.6, 0.0]", exact_source)
        self.assertIn("@assert fractional_values_rejected", exact_source)
        self.assertIn(
            "raw_values = value.(x; result=result_index)",
            live_source,
        )
        self.assertIn("bits = validated_binary_bits(raw_values)", live_source)
        self.assertLess(
            live_source.index(
                "raw_values = value.(x; result=result_index)"
            ),
            live_source.index("bits = validated_binary_bits(raw_values)"),
        )
        self.assertNotIn(
            "bits = round.(Int, value.(x; result=result_index))",
            live_source,
        )

    def test_environment_readme_makefile_and_bootstrap_are_linked(self) -> None:
        data = notebook()
        source = notebook_source()
        project = tomllib.loads(
            (REPO_ROOT / "notebooks_jl" / "Project.toml").read_text()
        )
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
        manifest = (REPO_ROOT / "notebooks_jl" / "Manifest.toml").read_text()
        readme = (REPO_ROOT / "README.md").read_text()
        makefile = (REPO_ROOT / "Makefile").read_text()
        bootstrap = (
            REPO_ROOT / "scripts" / "notebook_bootstrap.jl"
        ).read_text()

        self.assertEqual(
            "6e1d72ef-e149-4f5c-9c69-bc0273b92dbc",
            project["deps"]["QCIOpt"],
        )
        self.assertIn("[[deps.QCIOpt]]", manifest)
        self.assertIn(f'repo-rev = "{QCI_REVISION}"', manifest)
        self.assertIn(
            'repo-url = "https://github.com/SECQUOIA/QCIOpt.jl"',
            manifest,
        )
        self.assertIn("notebooks_jl/6-QCi.ipynb", readme)
        self.assertIn("make verify-qci-julia-local", readme)
        self.assertIn("verify-qci-julia-local:", makefile)
        self.assertIn("verify-qci-julia-cloud:", makefile)
        self.assertIn(
            "QUBONOTEBOOKS_QCI_ENABLE_CLOUD=0 "
            "QUBONOTEBOOKS_QCI_REQUIRE_CLOUD=0",
            makefile,
        )
        self.assertIn('UV_GROUP_FLAGS="--group docs"', makefile)
        self.assertIn('NOTEBOOKS="$(QCI_JULIA_NOTEBOOK)"', makefile)
        self.assertNotIn("qci", pyproject["dependency-groups"])
        self.assertNotIn("qiskit", pyproject["dependency-groups"])
        self.assertNotIn("conflicts", pyproject["tool"]["uv"])
        self.assertIn('"6-QCi" => :(using JuMP, QCIOpt)', bootstrap)
        self.assertNotIn("qci-client", bootstrap)
        self.assertIn(
            "env -u JULIA_CONDAPKG_BACKEND -u JULIA_PYTHONCALL_EXE",
            makefile,
        )
        self.assertIn('withenv("QCI_TOKEN" => nothing)', bootstrap)
        self.assertNotIn("qci-client>=", source)
        self.assertNotIn("pip install qci-client", source)
        self.assertNotIn("--group qci", source)
        self.assertIn(
            'Base.invokelatest('
            'QUBONotebooksBootstrap.bootstrap_notebook, "6-QCi")',
            source,
        )
        self.assertEqual(
            {"display_name": "Julia", "language": "julia", "name": "julia"},
            data["metadata"]["kernelspec"],
        )

    def test_committed_outputs_are_credential_free(self) -> None:
        data = notebook()
        code_cells = [
            cell for cell in data["cells"] if cell.get("cell_type") == "code"
        ]
        live_cell = notebook_cell(data, "qci-live")
        output_text = "\n".join(cell_output_text(cell) for cell in code_cells)

        self.assertTrue(code_cells)
        self.assertTrue(
            all(cell.get("execution_count") is not None for cell in code_cells)
        )
        self.assertIn("QCI cloud submission skipped", cell_output_text(live_cell))
        self.assertNotRegex(output_text, re.compile(r"(?i)bearer\s+[a-z0-9._-]+"))
        self.assertNotRegex(output_text, re.compile(r"(?i)\bjob[_ -]?id\b"))
        self.assertNotRegex(output_text, re.compile(r"(?i)\baccount\b"))


if __name__ == "__main__":
    unittest.main()
