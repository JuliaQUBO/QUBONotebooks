"""Shared notebook fixtures and extraction helpers for focused tests."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_notebooks.py"
MATHPROG_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "1-MathProg.ipynb"
QUBO_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "2-QUBO.ipynb"
QUBO_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "2-QUBO_python.ipynb"
GAMA_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "3-GAMA.ipynb"
GAMA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "3-GAMA_python.ipynb"
DWAVE_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "4-DWave.ipynb"
DWAVE_PYTHON_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "4-DWAVE_python.ipynb"
MATHPROG_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "1-MathProg_python.ipynb"
QCI_NOTEBOOK_PATH = REPO_ROOT / "notebooks_py" / "6-QCi_python.ipynb"
QCI_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "6-QCi.ipynb"
BENCHMARKING_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "5-Benchmarking.ipynb"
BENCHMARKING_PYTHON_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_py" / "5-Benchmarking_python.ipynb"
)
CANONICAL_PROBLEMS_JULIA_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_jl" / "7-CanonicalProblems.ipynb"
)
ORDER_PARTITIONING_JULIA_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_jl" / "8-OrderPartitioning.ipynb"
)
CANCER_GENOMICS_JULIA_NOTEBOOK_PATH = (
    REPO_ROOT / "notebooks_jl" / "9-CancerGenomics.ipynb"
)
QAOA_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "10-QAOA.ipynb"
ANNEALING_JULIA_NOTEBOOK_PATH = REPO_ROOT / "notebooks_jl" / "11-Annealing.ipynb"
BENCHMARKING_RESULTS_ARCHIVES = (
    REPO_ROOT / "notebooks_py" / "results.zip",
    REPO_ROOT / "notebooks_jl" / "results.zip",
)
JULIA_COLAB_NOTEBOOK_PATHS = (
    REPO_ROOT / "notebooks_jl" / "1-MathProg.ipynb",
    REPO_ROOT / "notebooks_jl" / "2-QUBO.ipynb",
    REPO_ROOT / "notebooks_jl" / "3-GAMA.ipynb",
    REPO_ROOT / "notebooks_jl" / "4-DWave.ipynb",
    REPO_ROOT / "notebooks_jl" / "5-Benchmarking.ipynb",
    QCI_JULIA_NOTEBOOK_PATH,
    CANONICAL_PROBLEMS_JULIA_NOTEBOOK_PATH,
    ORDER_PARTITIONING_JULIA_NOTEBOOK_PATH,
    CANCER_GENOMICS_JULIA_NOTEBOOK_PATH,
    QAOA_JULIA_NOTEBOOK_PATH,
    ANNEALING_JULIA_NOTEBOOK_PATH,
)
NOTEBOOK_DIRS = (
    REPO_ROOT / "notebooks_jl",
    REPO_ROOT / "notebooks_py",
)
SPEC = importlib.util.spec_from_file_location("verify_notebooks", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
verify_notebooks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_notebooks)


def notebook_source(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])


def notebook_output_text(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join(
        json.dumps(cell.get("outputs", []), ensure_ascii=False)
        for cell in notebook["cells"]
    )


def notebook_cell_source(path: Path, marker: str) -> str:
    notebook = json.loads(path.read_text())

    for cell in notebook["cells"]:
        source = "".join(cell.get("source", []))
        if marker in source:
            return source

    raise AssertionError(f"Could not find notebook cell containing {marker!r}")


def notebook_function_source(path: Path, function_name: str) -> str:
    cell_source = notebook_cell_source(path, f"def {function_name}(")
    function_start = cell_source.index(f"def {function_name}(")
    next_function = cell_source.find("\ndef ", function_start + 1)
    if next_function == -1:
        return cell_source[function_start:]
    return cell_source[function_start:next_function]


def notebook_function_definitions(
    path: Path,
    marker: str,
    names: set[str],
) -> object:
    """Compile selected top-level functions from one Python notebook cell."""
    cell_source = notebook_cell_source(path, marker)
    tree = ast.parse(cell_source)
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in names
    ]
    found = {node.name for node in selected}
    if found != names:
        raise AssertionError(f"missing notebook functions: {sorted(names - found)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    return compile(module, str(path), "exec")


def notebook_cell_sources(path: Path) -> list[str]:
    notebook = json.loads(path.read_text())
    return ["".join(cell.get("source", [])) for cell in notebook["cells"]]


def notebook_cells(path: Path) -> list[dict]:
    notebook = json.loads(path.read_text())
    return notebook["cells"]


def notebook_solution_output_texts(path: Path) -> list[str]:
    outputs = []

    for cell in notebook_cells(path):
        source = "".join(cell.get("source", []))
        if (
            cell.get("cell_type") == "code"
            and "# SOLUTION (hidden in workshop version):" in source
        ):
            stream_text = []
            for output in cell.get("outputs", []):
                if (
                    output.get("output_type") == "stream"
                    and output.get("name") == "stdout"
                ):
                    text = output.get("text", [])
                    stream_text.append("".join(text) if isinstance(text, list) else text)
            outputs.append("".join(stream_text))

    return outputs


BACK_TO_TOP_CELL = re.compile(
    r'<div align="center">\s*'
    r'<a href="#top-[0-9a-z-]+">\U0001f51d Go back to the top \U0001f51d</a>\s*'
    r"</div>\Z"
)


def is_notebook_footer(cell: dict) -> bool:
    """Whether a cell is a trailing footer rather than learning content.

    Matched narrowly on purpose: a substring test would accept a code cell or a
    lesson that merely mentions the phrase, and callers drop trailing footers
    when checking that a summary closes the learning content.
    """
    if cell.get("cell_type") != "markdown":
        return False
    if notebook_first_heading(cell) == "## Acknowledgments":
        return True
    return BACK_TO_TOP_CELL.fullmatch("".join(cell.get("source", [])).strip()) is not None


def notebook_markdown(path: Path) -> str:
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook_cells(path)
        if cell.get("cell_type") == "markdown"
    )


def notebook_paths() -> list[Path]:
    return sorted(path for directory in NOTEBOOK_DIRS for path in directory.glob("*.ipynb"))


def notebook_first_heading(cell: dict) -> str:
    source = "".join(cell.get("source", []))

    for line in source.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped

    return ""
