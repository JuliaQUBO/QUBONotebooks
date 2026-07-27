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
BOOTSTRAP_MARKER = "function load_qubonotebooks_bootstrap()"
KERNEL_NAME = "qubonotebooks-colab-smoke"
IJULIA_PROJECT = """\
[deps]
IJulia = "7073ff75-c697-5162-941a-fcdaad2a7d2a"
"""
EXPECTED_OUTPUT = (
    "Notebook project key: 7-CanonicalProblems",
    "Google Colab runtime detected: true",
    "Manifest Julia version: 1.10.11",
    "Refreshing Julia package registry",
    "Resolving Julia packages for current runtime Julia 1.12",
    "Instantiating Julia packages",
    "Notebook bootstrap complete",
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
            r"(?im)^\s+(?:Activating project at|Resolving package versions|"
            r"Precompiling project)"
        ),
    ),
    (
        "stack trace or failed-task printer output",
        re.compile(r"(?i)(?:Stacktrace:|SYSTEM: caught exception)"),
    ),
)


def julia_command() -> list[str]:
    configured = os.environ.get("JULIA_BIN", os.environ.get("JULIA", "julia"))
    command = shlex.split(configured)
    if not command:
        raise ValueError("JULIA_BIN/JULIA must name a Julia executable.")
    return command


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


def bootstrap_cell_source(repo_root: Path) -> str:
    notebook_path = repo_root / NOTEBOOK_PATH
    notebook = json.loads(notebook_path.read_text())
    matches = [
        text_value(cell.get("source"))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
        and BOOTSTRAP_MARKER in text_value(cell.get("source"))
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one bootstrap cell in {notebook_path}, found {len(matches)}."
        )
    return matches[0]


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


def validate_bootstrap_outputs(outputs: list[dict]) -> str:
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

    for expected in EXPECTED_OUTPUT:
        if expected not in rendered:
            failures.append(f"missing milestone: {expected}")

    for label, pattern in FORBIDDEN_OUTPUT:
        match = pattern.search(rendered)
        if match is not None:
            failures.append(f"{label}: {concise_line(match.group(0))}")

    if failures:
        raise AssertionError(
            "Colab bootstrap output validation failed:\n- " + "\n- ".join(failures)
        )
    return rendered


def write_cross_minor_fixture(repo_root: Path, workspace: Path) -> None:
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

    source_manifest = (repo_root / "notebooks_jl" / "Manifest.toml").read_text()
    fixture_manifest, replacements = re.subn(
        r'^julia_version = "[^"]+"',
        'julia_version = "1.10.11"',
        source_manifest,
        count=1,
        flags=re.MULTILINE,
    )
    if replacements != 1:
        raise ValueError("Could not pin the smoke-test manifest to Julia 1.10.11.")
    (notebooks_dir / "Manifest.toml").write_text(fixture_manifest)


def write_smoke_notebook(source: str, path: Path) -> None:
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "bootstrap",
                "metadata": {},
                "outputs": [],
                "source": source.splitlines(keepends=True),
            }
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
    source = bootstrap_cell_source(repo_root)
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
        smoke_notebook = workspace / "colab-bootstrap-smoke.ipynb"
        executed_notebook = output_dir / "colab-bootstrap-smoke.ipynb"

        write_cross_minor_fixture(repo_root, workspace)
        write_smoke_notebook(source, smoke_notebook)
        kernel_project.mkdir()
        kernel_project.joinpath("Project.toml").write_text(IJULIA_PROJECT)
        output_dir.mkdir()

        env = os.environ.copy()
        env.update(
            {
                "COLAB_RELEASE_TAG": "ci-colab-bootstrap",
                "JULIA_PKG_PRECOMPILE_AUTO": "0",
                "QUBONOTEBOOKS_PRECOMPILE": "0",
                "QUBONOTEBOOKS_REPO_DIR": str(workspace),
                "QUBONOTEBOOKS_WARM_PACKAGES": "0",
            }
        )
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
                    "JULIA_PKG_PRECOMPILE_AUTO",
                    "QUBONOTEBOOKS_PRECOMPILE",
                    "QUBONOTEBOOKS_REPO_DIR",
                    "QUBONOTEBOOKS_WARM_PACKAGES",
                )
                if key in env
            },
        )

        jupyter_env = env.copy()
        jupyter_env["JUPYTER_PATH"] = str(kernels_root)
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
        rendered = validate_bootstrap_outputs(executed["cells"][0]["outputs"])
        print("Captured first-cell output:", flush=True)
        print(rendered.rstrip(), flush=True)

    print("Julia 1.12 Colab bootstrap output smoke passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
