"""Behavioral checks for workshop answers, packaging, and source preservation."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "export_workshops", REPO_ROOT / "scripts" / "export_workshops.py"
)
exporter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(exporter)


def notebook_fixture():
    def code(source, *, tags=()):
        return {
            "cell_type": "code", "metadata": {"tags": list(tags)},
            "source": [source], "execution_count": 3,
            "outputs": [{"output_type": "stream", "name": "stdout", "text": "answer\n"}],
        }

    return {
        "nbformat": 4, "nbformat_minor": 5,
        "metadata": {"widgets": {"saved-answer": "answer"}},
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": [
                '<a href="https://colab.research.google.com/github/example/repo/blob/main/lesson.ipynb"><img src="badge.svg" /></a>'
            ]},
            code("print('worked example')"),
            code("# EXERCISE 1\n# Your code here"),
            code("print('tagged answer')", tags=("solution", "hide-cell")),
            code("# SOLUTION (hidden in workshop version):\nprint('untagged answer')"),
            code("print('setup')", tags=("installation", "hide-cell")),
        ],
    }


class WorkshopExportTests(unittest.TestCase):
    def test_student_removes_answers_but_keeps_worked_examples(self):
        source = notebook_fixture()
        original = copy.deepcopy(source)
        student, count = exporter.workshop_notebook(source, "student")
        self.assertEqual(count, 2)
        self.assertEqual(len(student["cells"]), 4)
        self.assertEqual(student["cells"][1], source["cells"][1])
        self.assertEqual(student["cells"][2]["outputs"], [])
        self.assertIsNone(student["cells"][2]["execution_count"])
        self.assertNotIn("widgets", student["metadata"])
        self.assertNotIn("colab.research.google.com/github/", "".join(student["cells"][0]["source"]))
        self.assertEqual(source, original)

    def test_instructor_reveals_answers_and_keeps_setup_hidden(self):
        source = notebook_fixture()
        source["cells"][3]["metadata"].update(
            collapsed=True, jupyter={"source_hidden": True, "outputs_hidden": True}
        )
        instructor, count = exporter.workshop_notebook(source, "instructor")
        self.assertEqual(count, 2)
        self.assertEqual(len(instructor["cells"]), len(source["cells"]))
        self.assertEqual(instructor["cells"][3]["outputs"], source["cells"][3]["outputs"])
        self.assertEqual(instructor["cells"][3]["metadata"], {"tags": ["solution"], "jupyter": {}})
        self.assertEqual(instructor["cells"][-1], source["cells"][-1])

    def test_tagged_markdown_solutions_are_removed(self):
        source = notebook_fixture()
        source["cells"].append({
            "cell_type": "markdown", "source": ["Worked answer"],
            "metadata": {"tags": ["solution"]},
        })
        result, count = exporter.workshop_notebook(source, "student")
        self.assertEqual(count, 3)
        self.assertEqual(len(result["cells"]), 4)

    def test_packages_are_repeatable_and_exclude_untracked_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()

            def git(*args):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)

            git("init", "--quiet")
            files = {
                "notebooks_py/lesson.ipynb": json.dumps(notebook_fixture()),
                "notebooks_data/input.csv": "x,y\n1,2\n",
                "scripts/notebook_bootstrap.jl": "# runtime fixture\n",
                "pyproject.toml": "[project]\nname='fixture'\n",
                "LICENSE": "license fixture\n",
                "README.md": "# Collection\n",
                "workshops.md": "# Workshop guide\n",
                "tests/answers.py": "# answers should not enter a student bundle\n",
            }
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
            git("add", *files)
            git("-c", "user.name=Workshop test", "-c", "user.email=workshop@example.invalid", "commit", "--quiet", "-m", "fixture")
            (root / "notebooks_py" / "credentials.txt").write_text("private untracked fixture")
            first = Path(temporary) / "first"
            second = Path(temporary) / "second"
            exporter.build_workshops(root, first, ("student", "instructor"))
            exporter.build_workshops(root, second, ("student", "instructor"))
            for edition in ("student", "instructor"):
                self.assertEqual((first / f"{edition}.zip").read_bytes(), (second / f"{edition}.zip").read_bytes())
                manifest = json.loads((first / edition / "workshop-manifest.json").read_text())
                self.assertFalse(manifest["source_has_local_changes"])
                self.assertEqual(set(manifest["files_sha256"]), set(files) - {"tests/answers.py"})
                for name, digest in manifest["files_sha256"].items():
                    self.assertEqual(hashlib.sha256((first / edition / name).read_bytes()).hexdigest(), digest)
                with zipfile.ZipFile(first / f"{edition}.zip") as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
                    self.assertEqual(set(archive.namelist()), {f"{edition}/{name}" for name in manifest["files_sha256"]} | {f"{edition}/workshop-manifest.json"})
            for name, content in files.items():
                self.assertEqual((root / name).read_text(), content)
            note = first / "student" / "notes.txt"
            note.write_text("learner's work")
            with self.assertRaises(FileExistsError):
                exporter.build_workshops(root, first, ("student",))
            self.assertEqual(note.read_text(), "learner's work")


if __name__ == "__main__":
    unittest.main()
