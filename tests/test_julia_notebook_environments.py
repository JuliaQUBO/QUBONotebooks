import json
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = REPO_ROOT / "notebooks_jl"
ENVIRONMENTS_DIR = NOTEBOOKS_DIR / "environments"

EXPECTED_DIRECT_DEPENDENCIES = {
    "1-MathProg": {
        "AmplNLWriter",
        "Bonmin_jll",
        "Cbc",
        "Couenne_jll",
        "GLPK",
        "Ipopt",
        "JuMP",
        "Plots",
        "SpecialFunctions",
    },
    "2-QUBO": {
        "DWave",
        "GLPK",
        "Graphs",
        "JuMP",
        "Karnak",
        "LinearAlgebra",
        "Luxor",
        "Plots",
        "QUBO",
    },
    "3-GAMA": {
        "BinaryWrappers",
        "DWave",
        "DelimitedFiles",
        "Downloads",
        "JuMP",
        "LinearAlgebra",
        "Measures",
        "NPZ",
        "Plots",
        "Random",
        "StatsBase",
        "StatsPlots",
        "lib4ti2_jll",
    },
    "4-DWave": {"DWave", "JuMP", "LinearAlgebra", "Plots", "QUBO"},
    "5-Benchmarking": {
        "DWave",
        "JSON",
        "JuMP",
        "LinearAlgebra",
        "Measures",
        "Plots",
        "QUBO",
        "Random",
        "Statistics",
        "StatsBase",
        "ZipFile",
    },
    "6-QCi": {"JuMP", "MathOptInterface", "QCIOpt"},
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


class JuliaNotebookEnvironmentTests(unittest.TestCase):

    def test_every_notebook_has_a_focused_project_and_two_manifests(self) -> None:
        self.assertEqual(
            set(EXPECTED_DIRECT_DEPENDENCIES),
            {path.stem for path in NOTEBOOKS_DIR.glob("*.ipynb")},
        )

        for project_key, expected_dependencies in EXPECTED_DIRECT_DEPENDENCIES.items():
            with self.subTest(project_key=project_key):
                project_dir = ENVIRONMENTS_DIR / project_key
                project = tomllib.loads((project_dir / "Project.toml").read_text())
                self.assertEqual(expected_dependencies, set(project["deps"]))

                manifest_110 = tomllib.loads(
                    (project_dir / "Manifest.toml").read_text()
                )
                manifest_112 = tomllib.loads(
                    (project_dir / "Manifest-v1.12.toml").read_text()
                )
                self.assertEqual("1.10.11", manifest_110["julia_version"])
                self.assertEqual("1.12.6", manifest_112["julia_version"])
                for manifest in (manifest_110, manifest_112):
                    self.assertTrue(
                        expected_dependencies.issubset(manifest["deps"]),
                        expected_dependencies - set(manifest["deps"]),
                    )

    def test_url_only_dependencies_keep_the_reviewed_revisions(self) -> None:
        for manifest_name in ("Manifest.toml", "Manifest-v1.12.toml"):
            with self.subTest(manifest_name=manifest_name):
                qci_manifest = tomllib.loads(
                    (
                        ENVIRONMENTS_DIR
                        / "6-QCi"
                        / manifest_name
                    ).read_text()
                )
                self.assertEqual(
                    "30a6074fdd5bd75c3f1cf965329edd01c67e63fe",
                    qci_manifest["deps"]["QCIOpt"][0]["repo-rev"],
                )

                for project_key in (
                    "2-QUBO",
                    "3-GAMA",
                    "4-DWave",
                    "5-Benchmarking",
                    "9-CancerGenomics",
                    "11-Annealing",
                ):
                    manifest = tomllib.loads(
                        (
                            ENVIRONMENTS_DIR
                            / project_key
                            / manifest_name
                        ).read_text()
                    )
                    self.assertEqual(
                        "v0.7.6",
                        manifest["deps"]["DWave"][0]["repo-rev"],
                    )

    def test_notebook_2_saved_status_is_focused(self) -> None:
        notebook = json.loads((NOTEBOOKS_DIR / "2-QUBO.ipynb").read_text())
        status_cells = [
            cell
            for cell in notebook["cells"]
            if "Pkg.status()" in "".join(cell.get("source", []))
        ]
        self.assertEqual(1, len(status_cells))
        output = json.dumps(status_cells[0].get("outputs", []))

        self.assertIn("environments/2-QUBO/Project.toml", output)
        self.assertIn("Karnak", output)
        self.assertNotIn("AmplNLWriter", output)
        self.assertNotIn("QCIOpt", output)
        self.assertNotIn("QiskitOpt", output)


if __name__ == "__main__":
    unittest.main()
