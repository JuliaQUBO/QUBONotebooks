"""Regression checks for the repository's test-design policy."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TESTS_DIR = Path(__file__).resolve().parent


class TestDesignContractTests(unittest.TestCase):
    def test_substring_assertions_stay_below_forty_percent(self) -> None:
        assertions = []
        substring_assertions = []

        for path in TESTS_DIR.glob("test_*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            calls = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr.startswith("assert")
            ]
            assertions.extend(calls)
            substring_assertions.extend(
                node
                for node in calls
                if node.func.attr in {"assertIn", "assertNotIn"}
            )

        self.assertTrue(assertions)
        self.assertLess(len(substring_assertions) / len(assertions), 0.40)

    def test_focused_test_modules_remain_reviewable(self) -> None:
        line_counts = {
            path.name: len(path.read_text().splitlines())
            for path in TESTS_DIR.glob("test_*.py")
        }

        self.assertLess(max(line_counts.values()), 800, line_counts)
