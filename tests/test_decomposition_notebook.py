"""Independent application oracle, absence of stale results and release gates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "notebooks_jl/environments/12-Decomposition"
SPEC = importlib.util.spec_from_file_location("decomposition_gate", ROOT / "scripts/check_decomposition_release_gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class DecompositionNotebookTests(unittest.TestCase):
    def setUp(self):
        self.notebook = json.loads((ROOT / "notebooks_jl/12-Decomposition.ipynb").read_text())
        self.data = tomllib.loads((ROOT / "notebooks_data/decomposition_platform.toml").read_text())

    def test_source_reference_and_coordination_barrier(self):
        # Independent source arithmetic, never production fixing/lifting code.
        b, c, cost = self.data["base"], self.data["platform_increment"], self.data["platform_cost"]
        self.assertEqual((len(b), len(c)), (8, 8))
        self.assertTrue(all(len(row) == 6 for row in b+c))
        branches = [sum(max(base+platform*y for base, platform in zip(row_b, row_c)) for row_b, row_c in zip(b,c))-cost*y for y in (0,1)]
        self.assertEqual(branches, [205,259])
        choices = [max(range(6), key=lambda i:b[g][i]) for g in range(8)]
        self.assertEqual(choices, [0]*8)
        # At the best y=0 assignment, every departmental choice is optimal,
        # while the platform singleton alone loses its positive activation cost.
        incumbent = sum(b[g][choices[g]] for g in range(8))
        self.assertEqual(incumbent, 205)
        self.assertEqual(sum(c[g][choices[g]] for g in range(8))-cost, -60)
        self.assertEqual(max(branches)-incumbent, 54)

    def test_full_problem_precedes_code_and_single_large_search_cell(self):
        first_code = next(i for i,c in enumerate(self.notebook["cells"]) if c["cell_type"]=="code")
        introduction = "".join("".join(c["source"]) for c in self.notebook["cells"][:first_code])
        self.assertIn(r"x_{gi}\in\{0,1\}", introduction)
        self.assertIn(r"y\in\{0,1\}", introduction)
        self.assertIn("49 original binary variables", introduction)
        self.assertIn("max_variables=6", introduction)
        code = ["".join(c["source"]) for c in self.notebook["cells"] if c["cell_type"]=="code"]
        self.assertEqual(sum("DA.correctness_demo()" in s for s in code),1)
        self.assertFalse(any("run_attempt(" in s for s in code))
        self.assertFalse(any("binary_states(" in s for s in code))

    def test_no_exercises_bad_penalty_or_old_status_override(self):
        for cell in self.notebook["cells"]:
            source = "".join(cell["source"])
            self.assertNotRegex(source,r"(?m)^\s*#\s*(EXERCISE|SOLUTION)\b")
            self.assertFalse({"exercise","solution"} & set(cell["metadata"].get("tags",[])))
        implementation=(ROOT / "scripts/decomposition_application.jl").read_text()
        self.assertNotIn("ConstraintEncodingPenaltyHint",implementation)
        self.assertNotIn("MaxPenaltyUpdates",implementation)
        self.assertNotRegex(implementation,r"function\s+MOI\.get")
        self.assertIn("ToQUBO.project_original_state",implementation)
        self.assertIn("ToQUBO.reformulation_metadata",implementation)

    def test_pending_is_explicit_and_cannot_pass_as_released_execution(self):
        gate=tomllib.loads((PROJECT / "RELEASE-GATES.toml").read_text())
        project=tomllib.loads((PROJECT / "Project.toml").read_text())
        self.assertNotIn("sources",project)
        self.assertIn("HiGHS",project["deps"])
        if gate["status"]=="pending":
            self.assertTrue(GATE.readiness_errors())
            self.assertEqual(gate["decomposition_version"],"")
            self.assertIn("pending",self.notebook["metadata"]["qubonotebooks_execution_status"])
            self.assertTrue(all(not c.get("outputs") for c in self.notebook["cells"] if c["cell_type"]=="code"))
            return
        self.assertEqual(GATE.readiness_errors(),[])
        report=tomllib.loads((ROOT / "notebooks_data/decomposition_comparison/summary.toml").read_text())
        self.assertEqual(len(report["attempts"]),16)
        for path, expected in report["plan"]["input_hashes"].items():
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),expected,path)
        for method in ("direct_mip","separator_mip","partition_mip","separator_exact"):
            rows=[row for row in report["attempts"] if row["method"]==method]
            self.assertEqual(sorted(row["repetition"] for row in rows),[0,1,2,3])
            for row in rows:
                if "source_objective" not in row:
                    self.assertEqual(row["outcome"],"failed")
                    continue
                if row["source_feasible"]:
                    self.assertEqual(row["source_optimum"],259)
                    self.assertEqual(row["source_gap"],259-row["source_objective"])
                if method=="partition_mip":
                    self.assertFalse(row["logical_global_proof"])
                if row["logical_global_proof"]:
                    self.assertEqual(row["public_status"],"OPTIMAL")
        correctness=next(c for c in self.notebook["cells"] if c["id"]=="decomposition-correctness")
        self.assertTrue(correctness["outputs"],"Final tutorial needs genuine fresh-kernel outputs")
