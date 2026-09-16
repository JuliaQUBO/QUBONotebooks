"""Reject stale, infeasible, or incorrect MathProg solver results.

The solver-enabled CI lane runs these checks with the real Pyomo model API.
All fixture quantities are dimensionless, as in the tutorial models.
"""

import importlib.util
import math
import unittest

from notebook_test_support import MATHPROG_NOTEBOOK_PATH, notebook_function_definitions


@unittest.skipUnless(importlib.util.find_spec("pyomo"), "requires the mathprog dependency group")
class MathProgResultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pyomo.environ as pyo
        from pyomo.opt import SolverResults, SolverStatus, TerminationCondition

        cls.pyo = pyo
        cls.results_type = SolverResults
        cls.status = SolverStatus
        cls.termination = TerminationCondition
        namespace = {"pyo": pyo, "math": math}
        exec(notebook_function_definitions(
            MATHPROG_NOTEBOOK_PATH, "def check_solution(", {"check_solution"}
        ), namespace)
        cls.check_solution = staticmethod(namespace["check_solution"])

    def setUp(self):
        self.model = self.pyo.ConcreteModel()
        self.model.x = self.pyo.Var(domain=self.pyo.NonNegativeIntegers, initialize=2)
        self.model.limit = self.pyo.Constraint(expr=self.model.x <= 3)
        self.model.obj = self.pyo.Objective(expr=2 * self.model.x)
        self.results = self.results_type()
        self.results.solver.status = self.status.ok
        self.results.solver.termination_condition = self.termination.optimal

    def test_valid_result_and_feasibility_only_check(self):
        self.check_solution(self.model, self.results, 4)
        self.check_solution(self.model, self.results)

    def test_failed_solve_does_not_reuse_previous_values(self):
        self.results.solver.termination_condition = self.termination.maxTimeLimit
        with self.assertRaises(RuntimeError):
            self.check_solution(self.model, self.results, 4)

    def test_incorrect_objective_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, "Unexpected objective"):
            self.check_solution(self.model, self.results, 5)

    def test_invalid_decisions_are_rejected_without_an_objective_baseline(self):
        for value in (float("nan"), float("inf"), -1, 1.5, 4):
            with self.subTest(value=value):
                self.model.x.set_value(value, skip_validation=True)
                with self.assertRaises(AssertionError):
                    self.check_solution(self.model, self.results)

    def test_constraint_lower_bound_and_variable_upper_bound(self):
        self.model.limit.set_value(self.model.x >= 3)
        with self.assertRaisesRegex(AssertionError, "Constraint lower bound"):
            self.check_solution(self.model, self.results)
        self.model.limit.deactivate()
        self.model.x.setub(1)
        with self.assertRaisesRegex(AssertionError, "Variable above"):
            self.check_solution(self.model, self.results)
