#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTEBOOKS = (
    Path("notebooks_py/2-QUBO_python.ipynb"),
    Path("notebooks_py/3-GAMA_python.ipynb"),
)
TIMEOUT_ENV = "QUBONOTEBOOKS_NOTEBOOK_TIMEOUT"
PYTHON_KERNEL_NAME = "qubonotebooks-python-local"
JULIA_KERNEL_NAME = "qubonotebooks-julia-local"
JULIA_PROJECT = REPO_ROOT / "notebooks_jl"


def parse_execution_timeout_seconds() -> int:
    value = os.environ.get(TIMEOUT_ENV, "1200")
    try:
        timeout_seconds = int(value)
    except ValueError as exc:
        raise ValueError(
            f"Invalid {TIMEOUT_ENV} value {value!r}: must be an integer number of seconds."
        ) from exc

    if timeout_seconds <= 0:
        raise ValueError(
            f"Invalid {TIMEOUT_ENV} value {value!r}: must be a positive integer number of seconds."
        )

    return timeout_seconds


def default_julia_depot_path() -> str:
    configured = os.environ.get("JULIA_DEPOT_PATH")
    if configured:
        return configured
    return os.pathsep.join([str(REPO_ROOT / ".julia-depot"), str(Path.home() / ".julia")])


def find_julia_executable() -> str:
    return os.environ.get("JULIA_BIN", os.environ.get("JULIA", "julia"))


def merged_env(overrides: dict[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    if overrides:
        env.update(overrides)
    return env


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=REPO_ROOT, env=merged_env(env), check=True)


def output_dir() -> Path:
    path = REPO_ROOT / ".nbverify"
    path.mkdir(exist_ok=True)
    return path


def classify_notebook(path: Path) -> str:
    if "notebooks_py" in path.parts:
        return "python"
    if "notebooks_jl" in path.parts:
        return "julia"
    raise ValueError(f"Unsupported notebook path: {path}")


def instantiate_julia_project(julia_executable: str) -> None:
    run(
        [
            julia_executable,
            "--project=./notebooks_jl",
            "-e",
            "import Pkg; Pkg.instantiate()",
        ],
        env={
            "JULIA_DEPOT_PATH": default_julia_depot_path(),
            "JULIA_PKG_PRECOMPILE_AUTO": "0",
        },
    )


def python_kernel_spec_dir(tmpdir: Path) -> tuple[str, dict[str, str]]:
    kernels_dir = tmpdir / "kernels" / PYTHON_KERNEL_NAME
    kernels_dir.mkdir(parents=True, exist_ok=True)
    kernel_spec = {
        "argv": [
            sys.executable,
            "-m",
            "ipykernel_launcher",
            "-f",
            "{connection_file}",
        ],
        "display_name": "QUBONotebooks Python (local)",
        "language": "python",
        "interrupt_mode": "signal",
    }
    (kernels_dir / "kernel.json").write_text(json.dumps(kernel_spec, indent=2) + "\n")
    return PYTHON_KERNEL_NAME, {"JUPYTER_PATH": str(tmpdir)}


def julia_kernel_spec_dir(tmpdir: Path, *, julia_executable: str) -> tuple[str, dict[str, str]]:
    kernels_dir = tmpdir / "kernels" / JULIA_KERNEL_NAME
    kernels_dir.mkdir(parents=True, exist_ok=True)
    kernel_spec = {
        "argv": [
            julia_executable,
            "-i",
            "--color=yes",
            f"--project={JULIA_PROJECT}",
            "-e",
            "import IJulia; IJulia.run_kernel()",
            "{connection_file}",
        ],
        "display_name": "QUBONotebooks Julia (local)",
        "language": "julia",
        "env": {
            "JULIA_DEPOT_PATH": default_julia_depot_path(),
            "JULIA_PKG_PRECOMPILE_AUTO": "0",
        },
        "interrupt_mode": "signal",
    }
    (kernels_dir / "kernel.json").write_text(json.dumps(kernel_spec, indent=2) + "\n")
    env = {
        "JUPYTER_PATH": str(tmpdir),
        "JULIA_DEPOT_PATH": default_julia_depot_path(),
        "JULIA_PKG_PRECOMPILE_AUTO": "0",
    }
    return JULIA_KERNEL_NAME, env


def execute_notebook(
    path: Path,
    *,
    timeout_seconds: int,
    kernel_name: str | None = None,
    env: dict[str, str] | None = None,
) -> None:
    cmd = [
        sys.executable,
        "-m",
        "jupyter",
        "nbconvert",
        "--to",
        "notebook",
        "--execute",
        f"--ExecutePreprocessor.timeout={timeout_seconds}",
        "--output-dir",
        str(output_dir()),
    ]
    if kernel_name is not None:
        cmd.append(f"--ExecutePreprocessor.kernel_name={kernel_name}")
    cmd.append(str(path))
    run(cmd, env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute selected QUBONotebooks notebooks locally through Jupyter."
    )
    parser.add_argument(
        "notebooks",
        nargs="*",
        default=[str(path) for path in DEFAULT_NOTEBOOKS],
        help="Notebook paths relative to the repository root.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    notebooks = [Path(path) for path in args.notebooks]
    timeout_seconds = parse_execution_timeout_seconds()

    for notebook in notebooks:
        if not (REPO_ROOT / notebook).is_file():
            raise FileNotFoundError(f"Notebook not found: {notebook}")

    julia_notebooks = [path for path in notebooks if classify_notebook(path) == "julia"]
    python_notebooks = [path for path in notebooks if classify_notebook(path) == "python"]

    if python_notebooks:
        with tempfile.TemporaryDirectory(prefix="qubonotebooks-python-kernels-") as tmp:
            kernel_name, env = python_kernel_spec_dir(Path(tmp))
            for notebook in python_notebooks:
                execute_notebook(
                    notebook,
                    timeout_seconds=timeout_seconds,
                    kernel_name=kernel_name,
                    env=env,
                )

    if julia_notebooks:
        julia_executable = find_julia_executable()
        instantiate_julia_project(julia_executable)
        with tempfile.TemporaryDirectory(prefix="qubonotebooks-jupyter-kernels-") as tmp:
            kernel_name, env = julia_kernel_spec_dir(
                Path(tmp),
                julia_executable=julia_executable,
            )
            for notebook in julia_notebooks:
                execute_notebook(
                    notebook,
                    timeout_seconds=timeout_seconds,
                    kernel_name=kernel_name,
                    env=env,
                )

    print(f"Executed {len(notebooks)} notebook(s). Outputs written to {output_dir()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
