from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
MAKEFILE_PATH = REPO_ROOT / "Makefile"
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


class StarterSeriesNavigationTests(unittest.TestCase):
    def test_readme_documents_sequence_classification_and_attribution(self) -> None:
        readme = README_PATH.read_text()

        self.assertIn("Notebook 6 now has Julia and Python variants", readme)
        for classification in (
            "offline/portable",
            "local but heavyweight",
            "opt-in live data refresh",
            "opt-in IBM hardware",
            "opt-in D-Wave QPU",
        ):
            with self.subTest(classification=classification):
                self.assertIn(classification, readme)

        for url in (
            "https://doi.org/10.1287/educ.2025.0288",
            "https://arxiv.org/abs/2401.08989",
            "https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers",
        ):
            with self.subTest(url=url):
                self.assertIn(url, readme)

        self.assertIn("clean-room", readme.lower())

    def test_starter_notebooks_link_to_the_canonical_main_branch(self) -> None:
        for path in STARTER_NOTEBOOK_PATHS:
            with self.subTest(notebook=path.name):
                source = notebook_source(path)
                self.assertIn(COLAB_URL_TEMPLATE.format(name=path.stem), source)
                self.assertIn(
                    "https://github.com/JuliaQUBO/QUBONotebooks.git",
                    source,
                )
                self.assertNotRegex(
                    source,
                    r"github\.com/(?!JuliaQUBO/)[^/\s]+/QUBONotebooks",
                )
                self.assertNotIn("QUBONotebooks/blob/master/", source)


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
        bootstrap = BOOTSTRAP_PATH.read_text()
        match = re.search(
            r"const CREDENTIAL_FREE_DWAVE_NOTEBOOKS = Set\(\((.*?)\)\)",
            bootstrap,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        self.assertIn('"9-CancerGenomics"', match.group(1))
        self.assertIn('"11-Annealing"', match.group(1))
        self.assertIn('withenv("DWAVE_API_TOKEN" => nothing)', bootstrap)


class StarterSeriesVerificationTargetTests(unittest.TestCase):
    def test_makefile_exposes_local_aggregate_and_opt_in_targets(self) -> None:
        makefile = MAKEFILE_PATH.read_text()

        for target in (
            "verify-canonical-problems-julia:",
            "verify-order-partitioning-julia:",
            "verify-cancer-genomics-julia:",
            "verify-qaoa-julia-local:",
            "verify-annealing-julia-local:",
            "verify-five-starter-problems-julia-local:",
            "verify-qaoa-julia-ibm:",
            "verify-annealing-julia-qpu:",
        ):
            with self.subTest(target=target):
                self.assertIn(target, makefile)

        self.assertIn("FIVE_STARTER_JULIA_NOTEBOOKS", makefile)
        for path in STARTER_NOTEBOOK_PATHS:
            with self.subTest(notebook=path.name):
                self.assertIn(f"notebooks_jl/{path.name}", makefile)

        self.assertIn("QUBONOTEBOOKS_QAOA_ENABLE_IBM", makefile)
        self.assertIn("QUBONOTEBOOKS_QAOA_REQUIRE_IBM", makefile)
        self.assertIn("QUBONOTEBOOKS_QAOA_IBM_BACKEND", makefile)
        self.assertIn("QISKIT_IBM_TOKEN", makefile)
        self.assertIn("QUBONOTEBOOKS_ANNEALING_ENABLE_QPU", makefile)
        self.assertIn("QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU", makefile)
        self.assertIn("DWAVE_API_TOKEN", makefile)

        def recipe(target: str) -> str:
            match = re.search(
                rf"(?m)^{re.escape(target)}:\n((?:\t.*\n)+)",
                makefile,
            )
            self.assertIsNotNone(match)
            return match.group(1)

        self.assertIn(
            "QUBONOTEBOOKS_QAOA_ENABLE_IBM=0",
            recipe("verify-qaoa-julia-local"),
        )
        self.assertIn(
            "QUBONOTEBOOKS_QAOA_REQUIRE_IBM=0",
            recipe("verify-qaoa-julia-local"),
        )
        self.assertIn(
            "QUBONOTEBOOKS_ANNEALING_ENABLE_QPU=0",
            recipe("verify-annealing-julia-local"),
        )
        self.assertIn(
            "QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU=0",
            recipe("verify-annealing-julia-local"),
        )
        self.assertIn(
            "QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU=1",
            recipe("verify-annealing-julia-qpu"),
        )
        aggregate_recipe = recipe("verify-five-starter-problems-julia-local")
        self.assertIn("QUBONOTEBOOKS_QAOA_ENABLE_IBM=0", aggregate_recipe)
        self.assertIn("QUBONOTEBOOKS_QAOA_REQUIRE_IBM=0", aggregate_recipe)
        self.assertIn(
            "QUBONOTEBOOKS_ANNEALING_ENABLE_QPU=0",
            aggregate_recipe,
        )
        self.assertIn(
            "QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU=0",
            aggregate_recipe,
        )

    def test_readme_documents_targets_runtime_and_environment_contracts(self) -> None:
        readme = README_PATH.read_text()

        for target in (
            "verify-five-starter-problems-julia-local",
            "refresh-tcga-aml",
            "verify-qaoa-julia-ibm",
            "verify-annealing-julia-qpu",
        ):
            with self.subTest(target=target):
                self.assertIn(target, readme)

        self.assertIn("Expected runtime", readme)
        self.assertIn("Environment variables", readme)


class StarterSeriesSafetyTests(unittest.TestCase):
    def test_starter_notebooks_have_the_shared_pedagogy_structure(self) -> None:
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

    def test_optional_service_paths_follow_credential_free_results(self) -> None:
        cancer = notebook_source(STARTER_NOTEBOOK_PATHS[2], code_only=True)
        qaoa = notebook_source(STARTER_NOTEBOOK_PATHS[3], code_only=True)
        annealing = notebook_source(STARTER_NOTEBOOK_PATHS[4], code_only=True)
        bootstrap = (REPO_ROOT / "scripts" / "notebook_bootstrap.jl").read_text()

        self.assertNotIn("cbioportal.org", cancer.lower())
        self.assertNotIn("Downloads.download", cancer)
        self.assertIn("warm_notebook_packages!", cancer)
        self.assertIn('"9-CancerGenomics"', cancer)
        self.assertIn("warm_notebook_packages!", annealing)
        self.assertIn('"11-Annealing"', annealing)
        self.assertIn('withenv("DWAVE_API_TOKEN" => nothing)', bootstrap)
        self.assertLess(
            bootstrap.index('withenv("DWAVE_API_TOKEN" => nothing)'),
            bootstrap.index("Core.eval(Main, import_expr)"),
        )

        self.assertLess(
            qaoa.index("partition_result = run_and_check_qaoa!"),
            qaoa.index("ibm_hardware_requested ="),
        )
        self.assertLess(
            qaoa.index("ibm_hardware_requested ="),
            qaoa.index("dry_run=false"),
        )
        self.assertIn("QUBONOTEBOOKS_QAOA_REQUIRE_IBM", qaoa)

        self.assertLess(
            annealing.index("local_results ="),
            annealing.index("qpu_requested ="),
        )
        self.assertLess(
            annealing.index("qpu_requested ="),
            annealing.index("optimizer = DWave.Optimizer"),
        )
        self.assertIn("QUBONOTEBOOKS_ANNEALING_REQUIRE_QPU", annealing)


if __name__ == "__main__":
    unittest.main()
