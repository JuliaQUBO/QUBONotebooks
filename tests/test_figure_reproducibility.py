"""Contracts for the figure reproducibility check in CONTRIBUTING.md."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from notebook_test_support import REPO_ROOT


MODULE_PATH = REPO_ROOT / "scripts" / "check_figure_reproducibility.py"
SPEC = importlib.util.spec_from_file_location("check_figure_reproducibility", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
figures = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = figures
SPEC.loader.exec_module(figures)

TIMING_NOTEBOOK = "notebooks_py/3-GAMA_python.ipynb"
SEEDED_NOTEBOOKS = (
    "notebooks_py/2-QUBO_python.ipynb",
    "notebooks_py/4-DWAVE_python.ipynb",
    "notebooks_py/5-Benchmarking_python.ipynb",
)


def figure(payload: str, mime: str = "image/png") -> dict:
    return {"output_type": "display_data", "metadata": {}, "data": {mime: payload}}


def code_cell(source: str, *outputs: dict, tags: tuple[str, ...] = ()) -> dict:
    metadata = {"tags": list(tags)} if tags else {}
    return {
        "cell_type": "code",
        "metadata": metadata,
        "source": source,
        "outputs": list(outputs),
    }


def notebook(*cells: dict) -> dict:
    return {"cells": list(cells), "metadata": {}, "nbformat": 4, "nbformat_minor": 2}


class CompareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.committed = notebook(
            {"cell_type": "markdown", "metadata": {}, "source": "# Title"},
            code_cell("draw()", figure("AAA"), {"output_type": "stream", "text": "1 s"}),
            code_cell("time_plot()", figure("TTT"), tags=(figures.EXEMPT_TAG,)),
            code_cell("svg()", figure("<svg/>", "image/svg+xml")),
        )

    def executed(self) -> dict:
        return copy.deepcopy(self.committed)

    def test_accepts_reproduced_figures_whatever_the_other_outputs_say(self) -> None:
        executed = self.executed()
        executed["cells"][1]["outputs"][1]["text"] = "2 s"
        executed["cells"][1]["execution_count"] = 7

        self.assertEqual([], figures.compare("nb", self.committed, executed))

    def test_flags_a_changed_png(self) -> None:
        executed = self.executed()
        executed["cells"][1]["outputs"][0]["data"]["image/png"] = "BBB"

        self.assertEqual(
            ["nb: cell 1 has 1 of 1 figure(s) that re-execution did not reproduce."],
            figures.compare("nb", self.committed, executed),
        )

    def test_flags_a_changed_svg(self) -> None:
        executed = self.executed()
        executed["cells"][3]["outputs"][0]["data"]["image/svg+xml"] = "<svg id='x'/>"

        self.assertEqual(
            ["nb: cell 3 has 1 of 1 figure(s) that re-execution did not reproduce."],
            figures.compare("nb", self.committed, executed),
        )

    def test_joins_a_payload_stored_as_a_list_of_lines(self) -> None:
        executed = self.executed()
        executed["cells"][1]["outputs"][0]["data"]["image/png"] = ["A", "AA"]

        self.assertEqual([], figures.compare("nb", self.committed, executed))

    def test_skips_a_tagged_cell(self) -> None:
        executed = self.executed()
        executed["cells"][2]["outputs"][0]["data"]["image/png"] = "UUU"

        self.assertEqual([], figures.compare("nb", self.committed, executed))

    def test_flags_a_tag_on_a_cell_without_a_figure(self) -> None:
        self.committed["cells"][2]["outputs"] = []

        self.assertEqual(
            [
                f"nb: cell 2 is tagged {figures.EXEMPT_TAG!r} but stores no figure. "
                "Remove the tag."
            ],
            figures.compare("nb", self.committed, self.executed()),
        )

    def test_flags_a_figure_that_appeared_or_disappeared(self) -> None:
        executed = self.executed()
        executed["cells"][1]["outputs"].append(figure("CCC"))

        self.assertEqual(
            ["nb: cell 1 stores 1 figure(s), but re-execution produced 2."],
            figures.compare("nb", self.committed, executed),
        )

    def test_refuses_to_compare_copies_with_different_sources(self) -> None:
        edited = self.executed()
        edited["cells"][1]["source"] = "draw(seed=1)"
        retyped = self.executed()
        retyped["cells"][0]["cell_type"] = "raw"
        shorter = self.executed()
        shorter["cells"].pop()

        for label, executed in (("source", edited), ("type", retyped), ("length", shorter)):
            with self.subTest(label):
                messages = figures.compare("nb", self.committed, executed)
                self.assertEqual(1, len(messages))
                self.assertRegex(messages[0], r"^nb: the executed copy was not produced")


class MainTests(unittest.TestCase):
    def run_main(self, *args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            status = figures.main(list(args))
        return status, stdout.getvalue()

    def test_reports_a_missing_executed_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status, output = self.run_main(TIMING_NOTEBOOK, "--executed-dir", tmp)

        self.assertEqual(1, status)
        self.assertRegex(output, r"notebooks_py/3-GAMA_python\.ipynb: no executed copy at ")

    def test_accepts_an_executed_copy_identical_to_the_committed_notebook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = REPO_ROOT / TIMING_NOTEBOOK
            (Path(tmp) / source.name).write_text(source.read_text(encoding="utf-8"))
            status, output = self.run_main(TIMING_NOTEBOOK, "--executed-dir", tmp)

        self.assertEqual(0, status, output)

    def test_fails_when_one_of_several_notebooks_differs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in (TIMING_NOTEBOOK, SEEDED_NOTEBOOKS[0]):
                source = REPO_ROOT / name
                document = json.loads(source.read_text(encoding="utf-8"))
                if name == SEEDED_NOTEBOOKS[0]:
                    outputs = [
                        output
                        for cell in document["cells"]
                        for output in cell.get("outputs", [])
                        if "image/png" in output.get("data", {})
                    ]
                    outputs[0]["data"]["image/png"] = "changed"
                (Path(tmp) / source.name).write_text(json.dumps(document))
            status, output = self.run_main(
                TIMING_NOTEBOOK, SEEDED_NOTEBOOKS[0], "--executed-dir", tmp
            )

        self.assertEqual(1, status)
        self.assertRegex(output, r"^1 figure reproducibility problem\(s\):")


class CommittedNotebookTests(unittest.TestCase):
    """The committed notebooks carry what the check and CONTRIBUTING.md rely on."""

    def load(self, name: str) -> dict:
        return json.loads((REPO_ROOT / name).read_text(encoding="utf-8"))

    def test_every_tagged_cell_stores_a_figure(self) -> None:
        for path in sorted(REPO_ROOT.glob("notebooks_*/*.ipynb")):
            document = json.loads(path.read_text(encoding="utf-8"))
            for index, cell in enumerate(document["cells"]):
                if figures.is_exempt(cell):
                    with self.subTest(notebook=path.name, cell=index):
                        self.assertTrue(figures.cell_figures(cell))

    def test_the_timing_plots_are_the_only_exempt_cells_in_the_portable_notebooks(self) -> None:
        document = self.load(TIMING_NOTEBOOK)
        exempt = [
            "".join(cell["source"]) for cell in document["cells"] if figures.is_exempt(cell)
        ]

        self.assertEqual(2, len(exempt))
        for source in exempt:
            with self.subTest(source=source.splitlines()[0]):
                self.assertRegex(source, r"ylabel\('Time \[s\]'\)")
        self.assertFalse(
            any(figures.is_exempt(cell) for cell in self.load(SEEDED_NOTEBOOKS[0])["cells"])
        )

    def test_layouts_and_samplers_that_feed_figures_are_seeded(self) -> None:
        unseeded = []
        for name in SEEDED_NOTEBOOKS:
            for index, cell in enumerate(self.load(name)["cells"]):
                if cell["cell_type"] != "code":
                    continue
                for line in "".join(cell["source"]).splitlines():
                    if "spring_layout(" in line and "seed=" not in line:
                        unseeded.append((name, index, line.strip()))
                    if line.lstrip().startswith("nx.draw(") and "pos=" not in line:
                        unseeded.append((name, index, line.strip()))
        qubo_sampling = [
            line.strip()
            for cell in self.load(SEEDED_NOTEBOOKS[0])["cells"]
            if cell["cell_type"] == "code"
            for line in "".join(cell["source"]).splitlines()
            if "simAnnSampler.sample(" in line
        ]

        self.assertEqual([], unseeded)
        self.assertEqual(2, len(qubo_sampling))
        for line in qubo_sampling:
            with self.subTest(line=line):
                self.assertRegex(line, r"seed=314159\)$")


if __name__ == "__main__":
    unittest.main()
