from __future__ import annotations

import json
import os
import re
import subprocess
import unittest
from pathlib import Path

from makefile_support import command_with_assignment


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
BOOTSTRAP_PATH = REPO_ROOT / "scripts" / "notebook_bootstrap.jl"

STARTER_NOTEBOOK_IMPORTS = {
    "7-CanonicalProblems": {"JuMP", "Plots", "QUBO"},
    "8-OrderPartitioning": {"JuMP", "Printf", "QUBO"},
    "9-CancerGenomics": {
        "DWave",
        "JSON",
        "JuMP",
        "LinearAlgebra",
        "Logging",
        "Printf",
        "QUBO",
    },
    "10-QAOA": {"JuMP", "QiskitOpt"},
    "11-Annealing": {
        "DWave",
        "JSON",
        "JuMP",
        "LinearAlgebra",
        "Logging",
        "Printf",
        "QUBO",
    },
}
STARTER_NOTEBOOK_PATHS = tuple(
    REPO_ROOT / "notebooks_jl" / f"{name}.ipynb"
    for name in STARTER_NOTEBOOK_IMPORTS
)
ALL_NOTEBOOK_PATHS = tuple(
    sorted(
        path
        for directory in (
            REPO_ROOT / "notebooks_jl",
            REPO_ROOT / "notebooks_py",
        )
        for path in directory.glob("*.ipynb")
    )
)
COLAB_URL_TEMPLATE = (
    "https://colab.research.google.com/github/JuliaQUBO/QUBONotebooks/"
    "blob/main/notebooks_jl/{name}.ipynb"
)


def notebook(path: Path) -> dict:
    return json.loads(path.read_text())


def notebook_source(path: Path, *, code_only: bool = False) -> str:
    cells = notebook(path)["cells"]
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in cells
        if not code_only or cell.get("cell_type") == "code"
    )


class StarterSeriesBootstrapTests(unittest.TestCase):
    def test_bootstrap_warms_only_each_selected_notebooks_imports(self) -> None:
        bootstrap = BOOTSTRAP_PATH.read_text()

        for notebook_name, expected_imports in STARTER_NOTEBOOK_IMPORTS.items():
            with self.subTest(notebook=notebook_name):
                match = re.search(
                    rf'"{re.escape(notebook_name)}"\s*=>\s*:\(using\s+([^)]+)\)',
                    bootstrap,
                )
                self.assertIsNotNone(match)
                actual_imports = {
                    package.strip() for package in match.group(1).split(",")
                }
                self.assertEqual(expected_imports, actual_imports)

    def test_credential_free_dwave_warmups_mask_ambient_tokens(self) -> None:
        # Defect class: ambient D-Wave credentials leak into a supposedly
        # credential-free package warm-up before notebook execution begins.
        bootstrap = BOOTSTRAP_PATH.read_text()
        match = re.search(
            r"const CREDENTIAL_FREE_DWAVE_NOTEBOOKS = Set\(\((.*?)\)\)",
            bootstrap,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        credential_free_notebooks = set(re.findall(r'"([^"]+)"', match.group(1)))
        self.assertTrue(
            {"9-CancerGenomics", "11-Annealing"}.issubset(
                credential_free_notebooks
            )
        )
        self.assertRegex(
            bootstrap,
            r'withenv\("DWAVE_API_TOKEN"\s*=>\s*nothing\)',
        )


class StarterSeriesVerificationTargetTests(unittest.TestCase):
    def test_local_aggregate_selects_each_notebook_and_disables_remote_paths(
        self,
    ) -> None:
        env = os.environ.copy()
        env.pop("MAKEFLAGS", None)
        env.pop("MFLAGS", None)
        # Hostile ambient values must not turn the local aggregate into a
        # remote-service submission.
        env.update(
            {
                "QUBONOTEBOOKS_QAOA_ENABLE_IBM": "1",
                "QUBONOTEBOOKS_QAOA_REQUIRE_IBM": "1",
                "QUBONOTEBOOKS_ANNEALING_ENABLE_QPU": "1",
                "QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU": "1",
            }
        )
        completed = subprocess.run(
            ["make", "--dry-run", "verify-five-starter-problems-julia-local"],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        command = command_with_assignment(completed.stdout, "NOTEBOOKS")
        assignments = dict(
            token.split("=", 1) for token in command if "=" in token
        )
        expected_notebooks = {
            str(path.relative_to(REPO_ROOT)) for path in STARTER_NOTEBOOK_PATHS
        }

        self.assertEqual(
            expected_notebooks,
            set(assignments["NOTEBOOKS"].split()),
        )
        self.assertEqual("0", assignments["QUBONOTEBOOKS_QAOA_ENABLE_IBM"])
        self.assertEqual("0", assignments["QUBONOTEBOOKS_QAOA_REQUIRE_IBM"])
        self.assertEqual("0", assignments["QUBONOTEBOOKS_ANNEALING_ENABLE_QPU"])
        self.assertEqual("0", assignments["QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU"])

    def test_remote_hardware_targets_fail_closed_without_opt_in(self) -> None:
        env = os.environ.copy()
        env.pop("MAKEFLAGS", None)
        env.pop("MFLAGS", None)
        for variable in (
            "QUBONOTEBOOKS_QAOA_ENABLE_IBM",
            "QUBONOTEBOOKS_QAOA_REQUIRE_IBM",
            "QUBONOTEBOOKS_QAOA_IBM_BACKEND",
            "QISKIT_IBM_TOKEN",
            "QUBONOTEBOOKS_ANNEALING_ENABLE_QPU",
            "QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU",
            "DWAVE_API_TOKEN",
        ):
            env.pop(variable, None)

        for target, required_opt_in in (
            ("verify-qaoa-julia-ibm", "QUBONOTEBOOKS_QAOA_ENABLE_IBM"),
            ("verify-annealing-julia-qpu", "QUBONOTEBOOKS_ANNEALING_ENABLE_QPU"),
        ):
            with self.subTest(target=target):
                completed = subprocess.run(
                    ["make", target],
                    cwd=REPO_ROOT,
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(2, completed.returncode)
                self.assertIn(
                    required_opt_in,
                    completed.stdout + completed.stderr,
                )


class StarterSeriesSafetyTests(unittest.TestCase):
    def test_starter_notebooks_have_the_shared_pedagogy_structure(self) -> None:
        # Defect class: a starter notebook silently drops a required exercise or
        # navigation section while still remaining executable.
        required_headings = (
            "setup",
            "learning objectives",
            "prerequisites",
            "summary",
            "references",
        )

        for path in STARTER_NOTEBOOK_PATHS:
            with self.subTest(notebook=path.name):
                source = notebook_source(path).lower()
                for heading in required_headings:
                    self.assertRegex(source, rf"(?m)^#+\s+{re.escape(heading)}\b")
                code = notebook_source(path, code_only=True)
                self.assertEqual(3, code.count("# EXERCISE"))

    def test_notebooks_do_not_embed_secrets_accounts_or_service_names(self) -> None:
        # Defect class: committed notebook source or output leaks credentials,
        # host paths, accounts, or a machine-specific service identifier.
        secret_literal = re.compile(
            r"""(?im)^\s*
            (?:
                ENV\[[^\]]*(?:TOKEN|SECRET|API_KEY)[^\]]*\]
                |
                [A-Za-z_][A-Za-z0-9_]*(?:token|secret|api_key)[A-Za-z0-9_]*
            )
            \s*=\s*["'][^"']+["']
            """,
            re.VERBOSE,
        )
        token_value = re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9]{20,}|"
            r"dwx-[A-Za-z0-9]{20,})\b"
        )
        hard_coded_service = re.compile(
            r"""(?ix)["']
            (?:
                DW_2000Q_[^"']+
                |
                Advantage(?:2)?_system[^"']+
                |
                ibm_[a-z0-9_]+
            )
            ["']
            """,
        )
        personal_path = re.compile(r"C:\\\\Users|/Users/|/home/")

        for path in ALL_NOTEBOOK_PATHS:
            with self.subTest(notebook=path.name):
                code = notebook_source(path, code_only=True)
                source = notebook_source(path)
                outputs = json.dumps(
                    [
                        cell.get("outputs", [])
                        for cell in notebook(path)["cells"]
                        if cell.get("cell_type") == "code"
                    ]
                )
                self.assertNotRegex(code, secret_literal)
                self.assertNotRegex(code, r"\bsave_account\s*\(")
                self.assertNotRegex(code, hard_coded_service)
                self.assertNotRegex(outputs, token_value)
                self.assertNotRegex(source, personal_path)
                self.assertNotRegex(outputs, personal_path)
                self.assertNotRegex(
                    source,
                    r"github\.com/(?:pedromxavier/QUBO-notebooks|"
                    r"AlbertLee125/QUBONotebooks|SECQUOIA/QUBONotebooks)",
                )


if __name__ == "__main__":
    unittest.main()
