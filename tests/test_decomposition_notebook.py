"""Independent fixture oracles and the published decomposition/environment contract."""

import itertools
import json
from pathlib import Path
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "notebooks_jl/environments/12-Decomposition"
PIN = "3a9e78de5022a62b41fabdc9995e81c8e5cbb785"


def states(n):
    return itertools.product((0, 1), repeat=n)


class DecompositionNotebookTests(unittest.TestCase):
    def test_source_provenance_survives_both_runtime_locks(self):
        # Defect class: a refresh replaces a feature-complete immutable source
        # with floating main, a registry release, or a local checkout.
        project = tomllib.loads((PROJECT / "Project.toml").read_text())
        trees = []
        for name in ("Manifest.toml", "Manifest-v1.12.toml"):
            manifest = tomllib.loads((PROJECT / name).read_text())
            decomposition = manifest["deps"]["QUBODecomposition"][0]
            self.assertEqual(project["sources"]["QUBODecomposition"]["rev"], PIN)
            self.assertEqual(decomposition["repo-rev"], PIN)
            self.assertEqual(decomposition["repo-url"], project["sources"]["QUBODecomposition"]["url"])
            self.assertFalse(any("path" in entry for entries in manifest["deps"].values() for entry in entries))
            self.assertEqual(manifest["deps"]["ToQUBO"][0]["version"], "0.7.1")
            self.assertEqual(manifest["deps"]["QUBODrivers"][0]["version"], "0.6.5")
            self.assertEqual(manifest["deps"]["QUBOTools"][0]["version"], "0.16.2")
            trees.append(decomposition["git-tree-sha1"])
        self.assertEqual(trees[0], trees[1])

    def test_published_comparison_matches_independent_scalar_oracles(self):
        # Defect class: committed results drift from the independently known
        # original objective, while setup and notebook structure remain green.
        energy_a = lambda x: 5-3*x[0]+2*x[1]+4*x[0]*x[1]-x[2]-2*x[3]+2*x[2]*x[3]
        energy_b = lambda x: 3+sum(x)-2*sum(x[i]*x[i+1] for i in range(4))
        energy_c = lambda x: sum(x)-2*sum(x[i]*x[j] for i in range(6) for j in range(i+1,6))
        oracle_a = min(map(energy_a, states(4)))
        oracle_b = min(map(energy_b, states(5)))
        oracle_c = min(map(energy_c, states(6)))
        source = lambda x: 5+3*x[0]+2*x[1]
        oracle_d = lambda penalty: max(source(x)-penalty*(sum(x)-1)**2 for x in states(2))
        notebook = json.loads((ROOT / "notebooks_jl/12-Decomposition.ipynb").read_text())
        cell = next(cell for cell in notebook["cells"] if cell["id"] == "decomposition-comparison")
        tables = [output["data"]["text/markdown"] for output in cell["outputs"] if "text/markdown" in output.get("data", {})]
        self.assertEqual(len(tables), 1)
        table = "".join(tables[0]) if isinstance(tables[0], list) else tables[0]
        rows = [list(map(str.strip, line.strip("|").split("|"))) for line in table.splitlines()[2:]]
        expected = [(oracle_a,oracle_a), (oracle_a,oracle_a), (oracle_b,oracle_b), (oracle_b,oracle_b), (0,oracle_c), (oracle_d(0.1),oracle_d(0.1)), (oracle_d(10),oracle_d(10))]
        self.assertEqual(len(rows), len(expected))
        for row, (observed, optimum) in zip(rows, expected):
            self.assertAlmostEqual(float(row[1]), observed)
            self.assertAlmostEqual(float(row[2]), optimum)
            self.assertEqual(row[3], "LOCALLY_SOLVED")
            self.assertEqual(row[4], "false")
            self.assertLessEqual(int(row[6]), 32)
            self.assertLessEqual(int(row[7]), 32*256)
        self.assertEqual(max(source(x) for x in states(2) if sum(x)==1), 8)
        self.assertGreater(oracle_d(0.1), 8)
        self.assertEqual([min(energy_b(x) for x in states(5) if x[2]==s) for s in (0,1)], [3,0])
