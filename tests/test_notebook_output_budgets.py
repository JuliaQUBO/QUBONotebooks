"""Contracts for the committed-output size budgets in CONTRIBUTING.md."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from notebook_test_support import REPO_ROOT


BUDGETS_MODULE_PATH = REPO_ROOT / "scripts" / "check_notebook_output_budgets.py"
SPEC = importlib.util.spec_from_file_location(
    "check_notebook_output_budgets", BUDGETS_MODULE_PATH
)
assert SPEC is not None
assert SPEC.loader is not None
budgets = importlib.util.module_from_spec(SPEC)
# The module defines dataclasses, which resolve their annotations through
# sys.modules while the class body is processed.
sys.modules[SPEC.name] = budgets
SPEC.loader.exec_module(budgets)

KB = 1024
POLICY_DOCUMENT = REPO_ROOT / "CONTRIBUTING.md"


def policy_document(budget_rows: str, exception_rows: str) -> str:
    """Build a minimal policy document with the two tables the check reads."""
    return "\n".join(
        [
            "### Size budgets",
            "",
            "| Scope | Budget |",
            "| --- | --- |",
            budget_rows,
            "",
            "### Documented exceptions",
            "",
            "| Notebook | Scope | Granted ceiling | What the stored output is |",
            "| --- | --- | --- | --- |",
            exception_rows,
            "",
        ]
    )


DEFAULT_BUDGET_ROWS = "\n".join(
    [
        "| One code cell | 256 KB of stored output |",
        "| One notebook | 1.0 MB of stored output |",
        "| All notebooks | 10 MB of stored output |",
    ]
)


def measurement(notebook: str, *cell_sizes: int) -> object:
    return budgets.Measurement(
        notebook=notebook,
        stored_bytes=sum(cell_sizes),
        cell_bytes=tuple(enumerate(cell_sizes)),
    )


def policy(**grants: int) -> object:
    """Build the default budgets, with grants keyed as ``stem__scope``.

    ``a__cell=448 * KB`` grants 448 KB to one code cell of ``a.ipynb``.
    """
    scopes = {"cell": budgets.CELL_SCOPE, "notebook": budgets.NOTEBOOK_SCOPE}
    return budgets.Policy(
        budgets={
            budgets.CELL_SCOPE: 256 * KB,
            budgets.NOTEBOOK_SCOPE: 1024 * KB,
            budgets.COLLECTION_SCOPE: 10 * 1024 * KB,
        },
        grants={
            (f"{stem}.ipynb", scopes[scope]): ceiling
            for stem, scope, ceiling in (
                (*name.rsplit("__", 1), ceiling) for name, ceiling in grants.items()
            )
        },
    )


class PolicySizeTests(unittest.TestCase):
    def test_reads_kilobytes_and_fractional_megabytes(self) -> None:
        self.assertEqual(256 * KB, budgets.parse_size("256 KB of stored output"))
        self.assertEqual(1024 * KB, budgets.parse_size("1.0 MB"))
        self.assertEqual(2400 * KB, budgets.parse_size("2400 KB"))

    def test_rejects_a_size_without_a_unit_the_check_understands(self) -> None:
        for text in ("256", "256 bytes", "a lot", "0.5 GB"):
            with self.subTest(size=text):
                with self.assertRaisesRegex(ValueError, "Not a policy size"):
                    budgets.parse_size(text)


class PolicyParsingTests(unittest.TestCase):
    def test_reads_the_committed_budgets_and_exceptions(self) -> None:
        loaded = budgets.load_policy(POLICY_DOCUMENT.read_text())

        self.assertEqual(
            {budgets.CELL_SCOPE, budgets.NOTEBOOK_SCOPE, budgets.COLLECTION_SCOPE},
            set(loaded.budgets),
        )
        self.assertTrue(loaded.grants)
        for (notebook, scope), ceiling in loaded.grants.items():
            with self.subTest(notebook=notebook, scope=scope):
                self.assertTrue((REPO_ROOT / notebook).is_file())
                self.assertGreater(ceiling, loaded.budgets[scope])

    def test_requires_every_budget_scope(self) -> None:
        document = policy_document("| One notebook | 1.0 MB |", "")
        with self.assertRaisesRegex(ValueError, "missing scopes"):
            budgets.load_policy(document)

    def test_rejects_an_exception_scope_that_is_not_a_budget_scope(self) -> None:
        # Defect class: an exception row names a scope the check does not
        # measure, so the row reads as a granted allowance and enforces nothing.
        document = policy_document(
            DEFAULT_BUDGET_ROWS,
            "| `notebooks_py/2-QUBO_python.ipynb` | Two cells | 448 KB | plots |",
        )
        with self.assertRaisesRegex(ValueError, "not one of"):
            budgets.load_policy(document)

    def test_rejects_an_exception_to_the_collection_budget(self) -> None:
        document = policy_document(
            DEFAULT_BUDGET_ROWS,
            "| `notebooks_py/2-QUBO_python.ipynb` | All notebooks | 20 MB | plots |",
        )
        with self.assertRaisesRegex(ValueError, "takes no exception"):
            budgets.load_policy(document)

    def test_rejects_two_rows_granting_the_same_scope(self) -> None:
        document = policy_document(
            DEFAULT_BUDGET_ROWS,
            "\n".join(
                [
                    "| `notebooks_py/2-QUBO_python.ipynb` | One notebook | 2 MB | plots |",
                    "| `notebooks_py/2-QUBO_python.ipynb` | One notebook | 3 MB | plots |",
                ]
            ),
        )
        with self.assertRaisesRegex(ValueError, "Duplicate exception row"):
            budgets.load_policy(document)

    def test_rejects_a_section_without_a_table(self) -> None:
        document = "### Size budgets\n\nNo table here.\n\n### Documented exceptions\n"
        with self.assertRaisesRegex(ValueError, "no table"):
            budgets.load_policy(document)


class MeasurementTests(unittest.TestCase):
    def test_measures_stored_output_as_compact_utf8_json(self) -> None:
        # Defect class: the measurement drifts from the definition the policy
        # states, so the numbers in review stop matching the numbers in the doc.
        self.assertEqual(2, budgets.cell_output_bytes({"outputs": []}))
        self.assertEqual(2, budgets.cell_output_bytes({}))
        # Compact separators: an indented serialization would be longer.
        self.assertEqual(4, budgets.cell_output_bytes({"outputs": [{}]}))
        # Non-ASCII text counts its UTF-8 length rather than an escape sequence.
        self.assertEqual(
            1,
            budgets.cell_output_bytes({"outputs": [{"text": "é"}]})
            - budgets.cell_output_bytes({"outputs": [{"text": "e"}]}),
        )

    def test_measures_code_cells_only(self) -> None:
        notebook = {
            "cells": [
                {"cell_type": "markdown", "source": ["# Title"], "outputs": [{"text": "x"}]},
                {"cell_type": "code", "source": ["1"], "outputs": [{"text": "x"}]},
                {"cell_type": "code", "source": ["2"]},
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.ipynb"
            path.write_text(json.dumps(notebook))
            measured = budgets.measure_notebook(path)

        self.assertEqual([1, 2], [index for index, _size in measured.cell_bytes])
        self.assertEqual(2, measured.cell_bytes[1][1])
        self.assertEqual(measured.cell_bytes[0][1] + 2, measured.stored_bytes)
        self.assertEqual((1, measured.cell_bytes[0][1]), measured.largest_cell)


class BudgetViolationTests(unittest.TestCase):
    def test_accepts_a_notebook_inside_both_budgets(self) -> None:
        self.assertEqual(
            [],
            budgets.check(policy(), [measurement("a.ipynb", 200 * KB, 100 * KB)]),
        )

    def test_flags_a_cell_over_the_cell_budget(self) -> None:
        violations = budgets.check(
            policy(), [measurement("a.ipynb", 100 * KB, 300 * KB)]
        )

        self.assertEqual(1, len(violations))
        self.assertIn("cell 1 stores 300.0 KB", violations[0])
        self.assertIn("over the 256.0 KB budget", violations[0])

    def test_flags_a_notebook_over_the_notebook_budget(self) -> None:
        violations = budgets.check(
            policy(), [measurement("a.ipynb", *([200 * KB] * 6))]
        )

        self.assertEqual(1, len(violations))
        self.assertIn("stores 1.17 MB", violations[0])
        self.assertIn("over the 1.00 MB budget", violations[0])

    def test_a_grant_bounds_the_scope_it_covers(self) -> None:
        # Defect class: an exception is read as a waiver, so a granted notebook
        # or cell can keep growing with nothing left to report it.
        within = measurement("a.ipynb", 100 * KB, 400 * KB)
        past = measurement("a.ipynb", 100 * KB, 500 * KB)

        self.assertEqual([], budgets.check(policy(a__cell=448 * KB), [within]))
        violations = budgets.check(policy(a__cell=448 * KB), [past])

        self.assertEqual(1, len(violations))
        self.assertIn("over the 448.0 KB granted ceiling", violations[0])

    def test_flags_a_grant_that_is_no_longer_needed(self) -> None:
        # Defect class: a reduction lands and its exception row survives,
        # leaving the table describing an allowance nothing uses.
        violations = budgets.check(
            policy(a__notebook=1248 * KB),
            [measurement("a.ipynb", *([180 * KB] * 5))],
        )

        self.assertEqual(1, len(violations))
        self.assertIn("no longer needed", violations[0])
        self.assertIn("900.0 KB now fits the 1.00 MB budget", violations[0])

    def test_flags_a_grant_that_allows_less_than_the_budget(self) -> None:
        violations = budgets.check(
            policy(a__cell=100 * KB), [measurement("a.ipynb", 90 * KB)]
        )

        self.assertEqual(1, len(violations))
        self.assertIn("already allows", violations[0])

    def test_flags_a_grant_for_a_notebook_that_does_not_exist(self) -> None:
        violations = budgets.check(
            policy(gone__notebook=2 * 1024 * KB), [measurement("a.ipynb", 90 * KB)]
        )

        self.assertEqual(1, len(violations))
        self.assertIn("does not exist", violations[0])

    def test_flags_the_collection_total_and_takes_no_exception(self) -> None:
        measurements = [
            measurement(f"{index}.ipynb", *([180 * KB] * 5)) for index in range(12)
        ]

        violations = budgets.check(policy(), measurements)

        self.assertEqual(1, len(violations))
        self.assertIn("All notebooks: store 10.55 MB", violations[0])
        self.assertIn("takes no exception", violations[0])


class CommittedOutputBudgetTests(unittest.TestCase):
    def test_committed_notebooks_are_within_the_documented_budgets(self) -> None:
        # Defect class: a re-executed notebook commits a larger or duplicated
        # figure, which no other check sees because the book build never runs
        # a notebook and every source-level contract still holds.
        loaded = budgets.load_policy(POLICY_DOCUMENT.read_text())
        measurements = budgets.measure_repository()

        self.assertEqual(17, len(measurements))
        self.assertEqual([], budgets.check(loaded, measurements))


if __name__ == "__main__":
    unittest.main()
