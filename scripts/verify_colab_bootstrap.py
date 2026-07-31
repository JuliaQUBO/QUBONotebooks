#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = Path("notebooks_jl/7-CanonicalProblems.ipynb")
NOTEBOOK_PATHS = tuple(
    path.relative_to(REPO_ROOT)
    for path in sorted(
        (REPO_ROOT / "notebooks_jl").glob("*.ipynb"),
        key=lambda path: int(path.stem.split("-", 1)[0]),
    )
)
SELECTED_NOTEBOOKS_ENV = "QUBONOTEBOOKS_COLAB_NOTEBOOKS"
BOOTSTRAP_MARKER = "function load_qubonotebooks_bootstrap()"
ACTIVATION_MARKER = "Pkg.activate(JULIA_PROJECT_DIR"
IMPORT_CELL_MARKER = "QUBONOTEBOOKS_COLAB_IMPORT_CELL"
IMPORT_CELL_METADATA_KEY = "qubonotebooks_colab_import_id"
PACKAGE_IMPORT_PATTERN = re.compile(
    r"(?m)^\s*(?:@eval\s+)?(?:using|import)\s+[A-Za-z]"
)
KERNEL_NAME = "qubonotebooks-colab-smoke"
IJULIA_PROJECT = """\
[deps]
IJulia = "7073ff75-c697-5162-941a-fcdaad2a7d2a"
"""
EXPECTED_COMMON_OUTPUT = (
    "Google Colab runtime detected: true",
    "Manifest Julia version: 1.12.6",
    "Instantiating Julia packages",
    "Notebook bootstrap complete",
)
EXECUTION_FORBIDDEN_OUTPUT = (
    (
        "stack trace or failed-task printer output",
        re.compile(r"(?i)(?:Stacktrace:|SYSTEM: caught exception)"),
    ),
    (
        "CondaPkg environment setup",
        re.compile(r"(?i)(?:CondaPkg|micromamba|\bpixi\b|/\.CondaPkg)"),
    ),
    (
        "package precompilation output",
        re.compile(r"(?im)^\s*(?:\[ Info:\s*)?Precompiling\b"),
    ),
)
FORBIDDEN_OUTPUT = (
    (
        "repository or package clone progress",
        re.compile(r"(?im)^\s*Cloning (?:git-repo|into )"),
    ),
    (
        "package or artifact installation transcript",
        re.compile(
            r"(?im)^\s*(?:Installed |Installing \d+ artifacts?|"
            r"Downloaded artifact|Downloading artifact)"
        ),
    ),
    (
        "Pkg registry, project, or manifest update transcript",
        re.compile(r"(?im)^\s*(?:Updating registry at|Updating `|No Changes to `)"),
    ),
    (
        "unsuppressed Pkg progress",
        re.compile(
            r"(?im)^\s*(?:Activating project at|Resolving package versions|"
            r"(?:\[ Info:\s*)?Precompiling\b)"
        ),
    ),
    (
        "pip download progress",
        re.compile(r"(?m)^\s*[━╺╸]{3,}.*$"),
    ),
    (
        "Julia manifest mismatch warning",
        re.compile(r"(?i)manifest.+targets Julia.+current kernel"),
    ),
)


def julia_command() -> list[str]:
    configured = os.environ.get("JULIA_BIN", os.environ.get("JULIA", "julia"))
    command = shlex.split(configured)
    if not command:
        raise ValueError("JULIA_BIN/JULIA must name a Julia executable.")
    return command


def selected_notebook_paths(configured: str | None = None) -> tuple[Path, ...]:
    if configured is None:
        configured = os.environ.get(SELECTED_NOTEBOOKS_ENV, "")
    requested = tuple(filter(None, re.split(r"[,\s]+", configured.strip())))
    if not requested:
        return NOTEBOOK_PATHS

    available = {path.stem: path for path in NOTEBOOK_PATHS}
    unknown = [project_key for project_key in requested if project_key not in available]
    if unknown:
        raise ValueError(
            f"Unknown Julia notebook key(s): {', '.join(unknown)}. "
            f"Expected one or more of: {', '.join(available)}."
        )
    return tuple(available[project_key] for project_key in requested)


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    print("+", shlex.join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def text_value(value: object) -> str:
    if isinstance(value, list):
        return "".join(str(part) for part in value)
    if value is None:
        return ""
    return str(value)


def marked_code_cell(
    repo_root: Path,
    notebook: Path,
    *,
    marker: str,
    description: str,
    smoke_id: str,
) -> dict[str, str]:
    notebook_path = repo_root / notebook
    data = json.loads(notebook_path.read_text())
    matches = [
        cell
        for cell in data["cells"]
        if cell.get("cell_type") == "code"
        and marker in text_value(cell.get("source"))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one {description} cell in {notebook_path}, "
            f"found {len(matches)}."
        )
    return {"id": smoke_id, "source": text_value(matches[0].get("source"))}


def bootstrap_cell_source(
    repo_root: Path,
    notebook: Path = NOTEBOOK_PATH,
) -> str:
    return marked_code_cell(
        repo_root,
        notebook,
        marker=BOOTSTRAP_MARKER,
        description="bootstrap",
        smoke_id="bootstrap",
    )["source"]


def activation_cell_source(repo_root: Path, notebook: Path) -> str:
    source = marked_code_cell(
        repo_root,
        notebook,
        marker=ACTIVATION_MARKER,
        description="activation",
        smoke_id="activate",
    )["source"]
    if "Pkg.instantiate" not in source:
        raise ValueError(
            f"Activation cell in {repo_root / notebook} does not instantiate "
            "the notebook environment."
        )
    return source


def notebook_import_cells(repo_root: Path, notebook: Path) -> list[dict]:
    notebook_path = repo_root / notebook
    data = json.loads(notebook_path.read_text())
    import_cells = [
        cell
        for cell in data["cells"]
        if cell.get("cell_type") == "code"
        and (
            IMPORT_CELL_MARKER in text_value(cell.get("source"))
            or cell.get("metadata", {}).get(IMPORT_CELL_METADATA_KEY)
        )
    ]
    if not import_cells:
        raise ValueError(f"Expected at least one marked import cell in {notebook_path}.")

    import_ids = [
        cell.get("metadata", {}).get(IMPORT_CELL_METADATA_KEY)
        for cell in import_cells
    ]
    if any(not cell_id for cell_id in import_ids):
        raise ValueError(
            f"Every marked import cell in {notebook_path} must have "
            f"'{IMPORT_CELL_METADATA_KEY}' metadata."
        )
    if len(import_ids) != len(set(import_ids)):
        raise ValueError(f"Marked import cell ids are not unique in {notebook_path}.")
    if any(not str(cell_id).startswith("imports") for cell_id in import_ids):
        raise ValueError(
            f"Marked import cell ids in {notebook_path} must start with 'imports'."
        )
    missing_source_markers = [
        str(cell_id)
        for cell_id, cell in zip(import_ids, import_cells)
        if IMPORT_CELL_MARKER not in text_value(cell.get("source"))
    ]
    if missing_source_markers:
        raise ValueError(
            f"Marked import cell(s) in {notebook_path} are missing the source marker: "
            + ", ".join(missing_source_markers)
        )

    unmarked_imports = []
    for index, cell in enumerate(data["cells"], start=1):
        if cell.get("cell_type") != "code":
            continue
        source = text_value(cell.get("source"))
        if BOOTSTRAP_MARKER in source or ACTIVATION_MARKER in source:
            continue
        import_id = cell.get("metadata", {}).get(IMPORT_CELL_METADATA_KEY)
        if PACKAGE_IMPORT_PATTERN.search(source) and not import_id:
            unmarked_imports.append(str(cell.get("id") or f"cell-{index}"))
    if unmarked_imports:
        raise ValueError(
            f"Found unmarked package import cell(s) in {notebook_path}: "
            + ", ".join(unmarked_imports)
        )
    return import_cells


def smoke_cells(repo_root: Path, notebook: Path) -> list[dict[str, str]]:
    bootstrap = {
        "id": "bootstrap",
        "source": bootstrap_cell_source(repo_root, notebook),
    }
    activation = {
        "id": "activate",
        "source": activation_cell_source(repo_root, notebook),
    }
    imports = [
        {
            "id": str(cell["metadata"][IMPORT_CELL_METADATA_KEY]),
            "source": text_value(cell.get("source")),
        }
        for cell in notebook_import_cells(repo_root, notebook)
    ]
    return [bootstrap, activation, *imports]


def output_text(outputs: list[dict]) -> str:
    return "".join(
        text_value(output.get("text"))
        for output in outputs
        if output.get("output_type") == "stream"
    )


def concise_line(text: str, *, limit: int = 240) -> str:
    line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    if len(line) <= limit:
        return line
    return line[: limit - 3] + "..."


def execution_output_failures(outputs: list[dict]) -> list[str]:
    failures: list[str] = []
    rendered = output_text(outputs)

    for output in outputs:
        output_type = output.get("output_type")
        if output_type == "error":
            failures.append(
                "cell error: "
                f"{output.get('ename', '<unknown>')}: {output.get('evalue', '')}"
            )
        elif output_type != "stream":
            failures.append(
                f"unexpected {output_type!r} output"
                + (
                    f": {concise_line(text_value(output.get('data')))}"
                    if output.get("data")
                    else ""
                )
            )

    for label, pattern in EXECUTION_FORBIDDEN_OUTPUT:
        match = pattern.search(rendered)
        if match is not None:
            failures.append(f"{label}: {concise_line(match.group(0))}")

    return failures


def validate_execution_outputs(outputs: list[dict]) -> str:
    failures = execution_output_failures(outputs)
    if failures:
        raise AssertionError(
            "Colab notebook execution validation failed:\n- " + "\n- ".join(failures)
        )
    return output_text(outputs)


def validate_notebook_execution(cells: list[dict]) -> None:
    failures: list[str] = []
    for index, cell in enumerate(cells, start=1):
        cell_id = cell.get("id", f"cell-{index}")
        failures.extend(
            f"cell {index} ({cell_id}): {failure}"
            for failure in execution_output_failures(cell.get("outputs", []))
        )
    if failures:
        raise AssertionError(
            "Colab notebook execution validation failed:\n- " + "\n- ".join(failures)
        )


def validate_bootstrap_outputs(
    outputs: list[dict],
    *,
    project_key: str = "7-CanonicalProblems",
) -> str:
    failures = execution_output_failures(outputs)
    rendered = output_text(outputs)

    expected_output = (
        f"Notebook project key: {project_key}",
        *EXPECTED_COMMON_OUTPUT,
    )
    for expected in expected_output:
        if expected not in rendered:
            failures.append(f"missing milestone: {expected}")

    for label, pattern in FORBIDDEN_OUTPUT:
        match = pattern.search(rendered)
        if match is not None:
            failures.append(f"{label}: {concise_line(match.group(0))}")

    warmup_message = "Loading notebook packages"
    if warmup_message in rendered:
        failures.append(f"unexpected eager package warm-up: {warmup_message}")

    if failures:
        raise AssertionError(
            "Colab bootstrap output validation failed:\n- " + "\n- ".join(failures)
        )
    return rendered


def write_colab_fixture(repo_root: Path, workspace: Path) -> None:
    scripts_dir = workspace / "scripts"
    notebooks_dir = workspace / "notebooks_jl"
    scripts_dir.mkdir(parents=True)
    notebooks_dir.mkdir(parents=True)

    shutil.copy2(
        repo_root / "scripts" / "notebook_bootstrap.jl",
        scripts_dir / "notebook_bootstrap.jl",
    )
    shutil.copy2(
        repo_root / "notebooks_jl" / "Project.toml",
        notebooks_dir / "Project.toml",
    )

    shutil.copy2(
        repo_root / "notebooks_jl" / "Manifest.toml",
        notebooks_dir / "Manifest.toml",
    )
    shutil.copy2(
        repo_root / "notebooks_jl" / "Manifest-v1.12.toml",
        notebooks_dir / "Manifest-v1.12.toml",
    )


def write_smoke_notebook(cells: list[dict[str, str]], path: Path) -> None:
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "id": cell["id"],
                "metadata": {},
                "outputs": [],
                "source": cell["source"].splitlines(keepends=True),
            }
            for cell in cells
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "QUBONotebooks Colab smoke",
                "language": "julia",
                "name": KERNEL_NAME,
            },
            "language_info": {"name": "julia"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path.write_text(json.dumps(notebook, indent=2) + "\n")


def write_kernel_spec(
    kernels_root: Path,
    *,
    julia: list[str],
    kernel_project: Path,
    kernel_env: dict[str, str],
) -> None:
    kernel_dir = kernels_root / "kernels" / KERNEL_NAME
    kernel_dir.mkdir(parents=True)
    kernel_spec = {
        "argv": [
            *julia,
            "-i",
            "--startup-file=no",
            "--color=no",
            f"--project={kernel_project}",
            "-e",
            "import IJulia; IJulia.run_kernel()",
            "{connection_file}",
        ],
        "display_name": "QUBONotebooks Colab smoke",
        "language": "julia",
        "env": kernel_env,
        "interrupt_mode": "signal",
    }
    (kernel_dir / "kernel.json").write_text(json.dumps(kernel_spec, indent=2) + "\n")


def verify_julia_1_12(julia: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        [
            *julia,
            "--startup-file=no",
            "-e",
            'print("$(VERSION.major).$(VERSION.minor)")',
        ],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    version = completed.stdout.strip()
    if version != "1.12":
        raise RuntimeError(f"Expected Julia 1.12 for the Colab smoke, got {version}.")


def verify_colab_stderr_suppression(
    julia: list[str],
    *,
    bootstrap_path: Path,
    cwd: Path,
    env: dict[str, str],
) -> None:
    sentinel = "COLAB_STDERR_SENTINEL"
    program = """
        include(ARGS[1])
        QUBONotebooksBootstrap.with_package_operation_io(true) do pkg_io
            pkg_io === devnull || error("Colab package IO was not devnull")
            println(stderr, ARGS[2])
        end
    """
    completed = subprocess.run(
        [
            *julia,
            "--startup-file=no",
            "-e",
            program,
            str(bootstrap_path),
            sentinel,
        ],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    if sentinel in completed.stdout or sentinel in completed.stderr:
        raise AssertionError("Colab package operation leaked process stderr.")


def main() -> int:
    repo_root = REPO_ROOT
    julia = julia_command()
    timeout = os.environ.get("QUBONOTEBOOKS_NOTEBOOK_TIMEOUT", "1200")
    startup_timeout = os.environ.get(
        "QUBONOTEBOOKS_KERNEL_STARTUP_TIMEOUT",
        "300",
    )

    with tempfile.TemporaryDirectory(prefix="qubonotebooks-colab-smoke-") as tmp:
        temp_root = Path(tmp)
        workspace = temp_root / "workspace"
        kernel_project = temp_root / "ijulia"
        kernels_root = temp_root / "jupyter"
        output_dir = temp_root / "output"

        write_colab_fixture(repo_root, workspace)
        kernel_project.mkdir()
        kernel_project.joinpath("Project.toml").write_text(IJULIA_PROJECT)
        output_dir.mkdir()

        env = os.environ.copy()
        env.setdefault("COLAB_RELEASE_TAG", "ci-colab-bootstrap")
        env["QUBONOTEBOOKS_REPO_DIR"] = str(workspace)
        for variable in (
            "JULIA_PKG_PRECOMPILE_AUTO",
            "QUBONOTEBOOKS_PRECOMPILE",
            "QUBONOTEBOOKS_WARM_PACKAGES",
        ):
            env.pop(variable, None)
        verify_julia_1_12(julia, cwd=workspace, env=env)
        verify_colab_stderr_suppression(
            julia,
            bootstrap_path=workspace / "scripts" / "notebook_bootstrap.jl",
            cwd=workspace,
            env=env,
        )
        run(
            [
                *julia,
                "--startup-file=no",
                f"--project={kernel_project}",
                "-e",
                "import Pkg; Pkg.instantiate(; io = devnull); import IJulia",
            ],
            cwd=workspace,
            env=env,
        )
        write_kernel_spec(
            kernels_root,
            julia=julia,
            kernel_project=kernel_project,
            kernel_env={
                key: env[key]
                for key in (
                    "COLAB_RELEASE_TAG",
                    "JULIA_DEPOT_PATH",
                    "QUBONOTEBOOKS_REPO_DIR",
                )
                if key in env
            },
        )

        jupyter_env = env.copy()
        jupyter_env["JUPYTER_PATH"] = str(kernels_root)
        notebook_paths = selected_notebook_paths()
        for notebook_path in notebook_paths:
            project_key = notebook_path.stem
            smoke_name = f"colab-{project_key.lower()}-smoke.ipynb"
            smoke_notebook = workspace / smoke_name
            executed_notebook = output_dir / smoke_name
            write_smoke_notebook(
                smoke_cells(repo_root, notebook_path),
                smoke_notebook,
            )
            run(
                [
                    sys.executable,
                    "-m",
                    "jupyter",
                    "nbconvert",
                    "--to",
                    "notebook",
                    "--execute",
                    f"--ExecutePreprocessor.timeout={timeout}",
                    f"--ExecutePreprocessor.startup_timeout={startup_timeout}",
                    f"--ExecutePreprocessor.kernel_name={KERNEL_NAME}",
                    f"--output-dir={output_dir}",
                    smoke_notebook.name,
                ],
                cwd=workspace,
                env=jupyter_env,
            )

            executed = json.loads(executed_notebook.read_text())
            validate_notebook_execution(executed["cells"])
            conda_environment = workspace / "notebooks_jl" / ".CondaPkg"
            if conda_environment.exists():
                raise AssertionError(
                    "Colab smoke unexpectedly created a CondaPkg environment at "
                    f"{conda_environment}."
                )
            bootstrap_outputs = executed["cells"][0].get("outputs", [])
            rendered = validate_bootstrap_outputs(
                bootstrap_outputs,
                project_key=project_key,
            )
            print(f"Captured {project_key} smoke output:", flush=True)
            print(rendered.rstrip(), flush=True)

    print(
        f"Julia 1.12 Colab bootstrap and import smokes passed for "
        f"{len(notebook_paths)} notebook(s).",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
