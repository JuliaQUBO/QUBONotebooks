from __future__ import annotations

import itertools
import json
import re
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "10-QAOA.ipynb"


def notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text())


def notebook_source() -> str:
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook()["cells"]
    )


def notebook_cell(data: dict, cell_id: str) -> dict:
    matches = [cell for cell in data["cells"] if cell.get("id") == cell_id]
    if len(matches) != 1:
        raise AssertionError(f"Expected one cell with id {cell_id!r}, found {len(matches)}")
    return matches[0]


def cell_output_text(cell: dict) -> str:
    output_parts = []
    for output in cell.get("outputs", []):
        value = output.get("text", output.get("data", {}).get("text/plain", ""))
        output_parts.append("".join(value) if isinstance(value, list) else value)
    return "\n".join(output_parts)


def binary_states(size: int) -> list[tuple[int, ...]]:
    return list(itertools.product((0, 1), repeat=size))


def qiskit_parameter_names(layers: int) -> list[str]:
    return [f"β[{layer}]" for layer in range(layers)] + [
        f"γ[{layer}]" for layer in range(layers)
    ]


def decode_qiskit_count_key(key: str) -> tuple[int, ...]:
    return tuple(int(bit) for bit in reversed(key.replace(" ", "")))


class QAOANotebookSourceTests(unittest.TestCase):
    def test_notebook_has_tutorial_structure_and_primary_references(self) -> None:
        source = notebook_source()
        required_sections = (
            "## Setup",
            "## Learning objectives",
            "## Prerequisites",
            "## QAOA in one convention",
            "## Three canonical models",
            "## Fixed-parameter circuits and resource audit",
            "## Run on IBM quantum hardware",
            "## Practice checkpoints",
            "## Summary",
            "## References",
        )

        for section in required_sections:
            with self.subTest(section=section):
                self.assertTrue(
                    section in source,
                    msg=f"missing tutorial section: {section}",
                )

        self.assertIn("https://arxiv.org/abs/1411.4028", source)
        self.assertIn("https://doi.org/10.1287/educ.2025.0288", source)
        self.assertIn("https://github.com/JuliaQUBO/QiskitOpt.jl", source)
        self.assertIn(
            "https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers",
            source,
        )
        self.assertIn("original Julia code and prose", source)

    def test_default_path_uses_supported_bounded_local_qiskitopt_api(self) -> None:
        source = notebook_source()
        required_markers = (
            "QiskitOpt.check_runtime(; local_backend=true, ibm=false)",
            "Model(QiskitOpt.QAOA.Optimizer)",
            "QiskitOpt.QUBODrivers.RandomSeed()",
            "QiskitOpt.QAOA.AerSeedSimulator()",
            "QiskitOpt.QAOA.TranspilerSeed()",
            "QiskitOpt.QAOA.fixed_parameter_circuit(",
            "QiskitOpt.QAOA.resource_audit(",
            "QiskitOpt.QAOA.count_key_bits(",
            "QiskitOpt's documented local default",
            "const QAOA_STANDARD_SEED = 73001",
            "const QAOA_LAYERS = 1",
            "const QAOA_OPTIMIZER_SHOTS = 256",
            "const QAOA_FINAL_SHOTS = 512",
            "const QAOA_MAX_ITERATIONS = 8",
            "partition_weights = [1, 3, 4, 8]",
            "maxcut_result = run_and_check_qaoa!(",
            "cover_result = run_and_check_qaoa!(",
        )

        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, source)

        self.assertNotIn("unsafe_backend", source)
        self.assertNotIn("PythonCall.pyimport", source)
        self.assertNotIn("QiskitOpt.qiskit", source)

    def test_ibm_handoff_is_explicit_secret_safe_and_backend_configurable(self) -> None:
        data = notebook()
        source = notebook_source()
        handoff_source = "".join(notebook_cell(data, "ibm-handoff")["source"])
        hardware_source = "".join(notebook_cell(data, "ibm-hardware")["source"])

        required_markers = (
            'ibm_hardware_requested = get(ENV, "QUBONOTEBOOKS_QAOA_ENABLE_IBM", "0") == "1"',
            'get(ENV, "QUBONOTEBOOKS_QAOA_IBM_BACKEND", "")',
            'get(ENV, "QISKIT_IBM_TOKEN", "")',
            'get(ENV, "QISKIT_IBM_INSTANCE", "")',
            'get(ENV, "QISKIT_IBM_CHANNEL", "")',
            'dry_run_backend = isempty(ibm_backend) ? "not-configured" : ibm_backend',
            "QiskitOpt.check_runtime(; local_backend=false, ibm=true, verbose=false)",
            "ibm_hardware_submitted = ibm_hardware.submitted",
            "if !requested",
            'isempty(backend) && push!(missing_configuration, "QUBONOTEBOOKS_QAOA_IBM_BACKEND")',
            '!token_is_configured && push!(missing_configuration, "QISKIT_IBM_TOKEN")',
            "err isa QiskitOpt.QAOA.RuntimeHandoffError",
            "failure=err.metadata",
            "backend=backend",
            "ibm_hardware_job = ibm_hardware_submitted ? ibm_hardware_run.job : nothing",
            "ibm_hardware_job.status()",
            "ibm_hardware_job.result()",
            "local Aer results above remain available",
        )
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertTrue(
                    marker in source,
                    msg=f"missing IBM hardware marker: {marker}",
                )

        self.assertTrue(
            "QiskitOpt.QAOA.ibm_runtime_handoff(" in handoff_source
            and "dry_run=true" in handoff_source,
            msg="the IBM preparation cell must exercise a dry run",
        )
        self.assertTrue(
            "QiskitOpt.QAOA.ibm_runtime_handoff(" in hardware_source
            and "dry_run=false" in hardware_source,
            msg="the hardware cell must contain a real IBM Runtime submission",
        )
        self.assertLess(
            hardware_source.index("if !requested"),
            hardware_source.index("dry_run=false"),
        )
        self.assertIsNone(re.search(r"\bsave_account\s*\(", source))
        self.assertNotIn("ibm_fez", source)
        self.assertNotIn("ibm_brisbane", source)
        self.assertNotIn("Bearer ", source)
        self.assertIsNone(re.search(r"(?i)\btoken\s*=\s*[\"'][^\"']+", source))

    def test_parameter_and_bit_order_are_programmatically_checked(self) -> None:
        source = notebook_source()

        self.assertEqual(["β[0]", "γ[0]"], qiskit_parameter_names(1))
        self.assertEqual(
            ["β[0]", "β[1]", "γ[0]", "γ[1]"],
            qiskit_parameter_names(2),
        )
        self.assertEqual((1, 0, 1, 0), decode_qiskit_count_key("0101"))
        self.assertEqual((0, 0, 1, 1), decode_qiskit_count_key("1100"))

        self.assertIn(
            '@assert p1_fixed_metadata["parameters"]["parameter_names"] == ["β[0]", "γ[0]"]',
            source,
        )
        self.assertIn(
            "@assert decoded_variable_bits == [1, 0, 1, 0]",
            source,
        )
        self.assertIn(
            '@assert p1_fixed_metadata["objective"]["qiskit_minimization_sign"] == 1',
            source,
        )

    def test_notebook_and_dependency_environment_are_linked(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()
        makefile = (REPO_ROOT / "Makefile").read_text()
        project = tomllib.loads((REPO_ROOT / "notebooks_jl" / "Project.toml").read_text())
        manifest = (REPO_ROOT / "notebooks_jl" / "Manifest.toml").read_text()
        sysimage = (REPO_ROOT / "scripts" / "create_sysimage.jl").read_text()

        self.assertEqual(
            "81b20daf-e62b-4502-a0d1-aa084de80e33",
            project["deps"]["QiskitOpt"],
        )
        self.assertEqual("0.7.1", project["compat"]["QiskitOpt"])
        self.assertIn("[[deps.QiskitOpt]]", manifest)
        self.assertIn('version = "0.7.1"', manifest)
        self.assertIn("notebooks_jl/10-QAOA.ipynb", readme)
        self.assertIn("make verify-qaoa-julia-local", readme)
        self.assertIn("environment-gated IBM hardware cell", readme)
        self.assertIn("verify-qaoa-julia-local:", makefile)
        self.assertIn('NOTEBOOKS="$(QAOA_JULIA_NOTEBOOK)"', makefile)
        self.assertIn('"QiskitOpt",', sysimage)


class QAOAMathematicalInvariantTests(unittest.TestCase):
    def test_number_partitioning_exact_baseline(self) -> None:
        weights = (1, 3, 4, 8)

        def raw_energy(bits: tuple[int, ...]) -> int:
            return sum(
                weight * (1 - 2 * bit) for weight, bit in zip(weights, bits)
            ) ** 2

        states = binary_states(len(weights))
        optimum = min(raw_energy(bits) for bits in states)
        optima = {bits for bits in states if raw_energy(bits) == optimum}

        self.assertEqual(0, optimum)
        self.assertEqual({(0, 0, 0, 1), (1, 1, 1, 0)}, optima)

    def test_maxcut_exact_baseline_and_sign(self) -> None:
        weighted_edges = (
            (1, 2, 2),
            (1, 3, 1),
            (2, 3, 2),
            (2, 4, 1),
            (3, 4, 3),
        )

        def cut_weight(bits: tuple[int, ...]) -> int:
            return sum(
                weight if bits[i - 1] != bits[j - 1] else 0
                for i, j, weight in weighted_edges
            )

        def raw_energy(bits: tuple[int, ...]) -> int:
            return -cut_weight(bits)

        states = binary_states(4)
        optimum = min(raw_energy(bits) for bits in states)
        optima = {bits for bits in states if raw_energy(bits) == optimum}

        self.assertEqual(-7, optimum)
        self.assertTrue(all(cut_weight(bits) == 7 for bits in optima))
        self.assertEqual(4, len(optima))

    def test_vertex_cover_exact_baseline_and_feasibility(self) -> None:
        edges = ((1, 2), (1, 3), (2, 3), (3, 4))
        penalty = 2

        def uncovered(bits: tuple[int, ...]) -> list[tuple[int, int]]:
            return [
                (i, j)
                for i, j in edges
                if bits[i - 1] == 0 and bits[j - 1] == 0
            ]

        def raw_energy(bits: tuple[int, ...]) -> int:
            return sum(bits) + penalty * len(uncovered(bits))

        states = binary_states(4)
        optimum = min(raw_energy(bits) for bits in states)
        optima = {bits for bits in states if raw_energy(bits) == optimum}

        self.assertEqual(2, optimum)
        self.assertEqual({(1, 0, 1, 0), (0, 1, 1, 0)}, optima)
        self.assertTrue(all(not uncovered(bits) for bits in optima))


class QAOANotebookOutputTests(unittest.TestCase):
    def test_notebook_commits_reproducible_local_outputs(self) -> None:
        data = notebook()
        code_cells = [cell for cell in data["cells"] if cell["cell_type"] == "code"]
        populated_cells = [cell for cell in code_cells if cell.get("outputs", [])]

        self.assertTrue(code_cells)
        self.assertEqual(
            list(range(1, len(code_cells) + 1)),
            [cell.get("execution_count") for cell in code_cells],
        )
        self.assertGreaterEqual(len(populated_cells), 12)
        self.assertEqual([], notebook_cell(data, "bootstrap").get("outputs", []))
        self.assertEqual([], notebook_cell(data, "activate").get("outputs", []))

        expected_output_markers = {
            "runtime-check": "Local runtime ready: QiskitOpt 0.7.1",
            "partition-run": "exact optimum raw energy = 0.0",
            "maxcut-run": "exact optimum raw energy = -7.0",
            "cover-run": "exact optimum raw energy = 2.0",
            "comparison": "Exact-versus-sampled energy summary",
            "fixed-circuits": "p=1 parameter order:",
            "resource-audits": "p=2 resources:",
            "bit-order": "QAOA.count_key_bits returns variable order",
            "ibm-handoff": "IBM handoff dry run:",
            "ibm-hardware": "IBM quantum hardware submission is disabled",
            "solution-bit-order": "Rendered key 1100 becomes variable-order bits",
        }
        for cell_id, marker in expected_output_markers.items():
            with self.subTest(cell_id=cell_id):
                self.assertIn(marker, cell_output_text(notebook_cell(data, cell_id)))

        self.assertFalse(
            any(
                output.get("output_type") == "error"
                for cell in code_cells
                for output in cell.get("outputs", [])
            )
        )

        serialized_outputs = json.dumps(
            [cell.get("outputs", []) for cell in code_cells], ensure_ascii=False
        )
        forbidden_markers = (
            "/home/",
            "/Users/",
            "C:\\Users",
            "AppData",
            "Bearer ",
            "QISKIT_IBM_TOKEN=",
            "QISKIT_IBM_INSTANCE=",
        )
        for marker in forbidden_markers:
            with self.subTest(marker=marker):
                self.assertNotIn(marker, serialized_outputs)


if __name__ == "__main__":
    unittest.main()
