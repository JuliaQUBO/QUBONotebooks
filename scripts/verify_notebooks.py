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
# Committed figures are compared byte for byte, and NumPy's AVX-512 kernels
# round differently from its AVX2 ones, which moves pixels. Capping the runtime
# dispatch here keeps a render identical across x86-64 machines.
NUMPY_DISPATCH_CAP = "X86_V3"
NUMPY_FEATURE_VARIABLES = ("NPY_DISABLE_CPU_FEATURES", "NPY_ENABLE_CPU_FEATURES")


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


def focused_julia_env(project: Path | None) -> dict[str, str]:
    if project is None:
        return {}
    # Select the notebook graph before IJulia loads any shared dependencies.
    # The aggregate environment supplies kernel tools absent from that graph.
    return {
        "JULIA_LOAD_PATH": os.pathsep.join(["@", str(JULIA_PROJECT), "@stdlib"]),
        "IJULIA_NODEFAULTKERNEL": "1",
    }


def instantiate_julia_project(julia_executable: str, *, project: Path | None = None) -> None:
    run(
        [
            julia_executable,
            f"--project={project}" if project is not None else "--project=./notebooks_jl",
            "-e",
            "import Pkg; Pkg.instantiate()",
        ],
        env={
            "JULIA_DEPOT_PATH": default_julia_depot_path(),
            "JULIA_PKG_PRECOMPILE_AUTO": "0",
            **focused_julia_env(project),
        },
    )


def numpy_dispatch_cap_env() -> dict[str, str]:
    """Return the environment that caps NumPy's dispatch at ``NUMPY_DISPATCH_CAP``.

    Only targets this machine supports are disabled: NumPy warns about the
    others, and the kernel treats warnings as errors. A NumPy-selection
    variable the caller already set is left alone.

    A render without the cap can differ from the committed figures, and the
    only later symptom is a reproducibility mismatch that reads as unseeded
    randomness, so every reason for declining is printed.
    """
    selected = [name for name in NUMPY_FEATURE_VARIABLES if name in os.environ]
    if selected:
        return uncapped(f"{selected[0]} is already set")
    try:
        from numpy._core._multiarray_umath import __cpu_dispatch__, __cpu_features__
    except ImportError:
        return uncapped("this NumPy does not expose numpy._core")
    dispatch = list(__cpu_dispatch__)
    if NUMPY_DISPATCH_CAP not in dispatch:
        return uncapped(
            f"{NUMPY_DISPATCH_CAP} is not a dispatch target of this NumPy build, "
            "which is the case on a non-x86-64 machine and before NumPy 2.4"
        )
    above_cap = dispatch[dispatch.index(NUMPY_DISPATCH_CAP) + 1 :]
    disabled = [target for target in above_cap if __cpu_features__.get(target)]
    if not disabled:
        return {}
    return {"NPY_DISABLE_CPU_FEATURES": " ".join(disabled)}


def uncapped(reason: str) -> dict[str, str]:
    print(
        f"No NumPy dispatch cap: {reason}. A figure this run renders may differ "
        "from the committed one.",
        flush=True,
    )
    return {}


def python_kernel_spec_dir(tmpdir: Path) -> tuple[str, dict[str, str]]:
    kernels_dir = tmpdir / "kernels" / PYTHON_KERNEL_NAME
    ipython_dir = tmpdir / "ipython"
    jupyter_config_dir = tmpdir / "jupyter-config"
    kernels_dir.mkdir(parents=True, exist_ok=True)
    ipython_dir.mkdir(parents=True, exist_ok=True)
    jupyter_config_dir.mkdir(parents=True, exist_ok=True)
    kernel_spec = {
        "argv": [
            sys.executable,
            str(REPO_ROOT / "scripts/start_python_kernel.py"),
            "-f",
            "{connection_file}",
        ],
        "display_name": "QUBONotebooks Python (local)",
        "language": "python",
        "interrupt_mode": "signal",
    }
    (kernels_dir / "kernel.json").write_text(json.dumps(kernel_spec, indent=2) + "\n")
    return PYTHON_KERNEL_NAME, {
        "JUPYTER_PATH": str(tmpdir),
        "JUPYTER_CONFIG_DIR": str(jupyter_config_dir),
        "IPYTHONDIR": str(ipython_dir),
        "PYTHONWARNINGS": "error",
        **numpy_dispatch_cap_env(),
    }


def julia_kernel_spec_dir(
    tmpdir: Path, *, julia_executable: str, project: Path | None = None,
) -> tuple[str, dict[str, str]]:
    kernels_dir = tmpdir / "kernels" / JULIA_KERNEL_NAME
    kernels_dir.mkdir(parents=True, exist_ok=True)
    kernel_spec = {
        "argv": [
            julia_executable,
            "-i",
            "--color=yes",
            f"--project={project if project is not None else JULIA_PROJECT}",
            "-e",
            "import IJulia; IJulia.run_kernel()",
            "{connection_file}",
        ],
        "display_name": "QUBONotebooks Julia (local)",
        "language": "julia",
        "env": {
            "JULIA_DEPOT_PATH": default_julia_depot_path(),
            "JULIA_PKG_PRECOMPILE_AUTO": "0",
            **focused_julia_env(project),
        },
        "interrupt_mode": "signal",
    }
    (kernels_dir / "kernel.json").write_text(json.dumps(kernel_spec, indent=2) + "\n")
    env = {
        "JUPYTER_PATH": str(tmpdir),
        "JULIA_DEPOT_PATH": default_julia_depot_path(),
        "JULIA_PKG_PRECOMPILE_AUTO": "0",
        **focused_julia_env(project),
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
    if kernel_name == PYTHON_KERNEL_NAME and sys.platform != "win32":
        from zmq import IPC_PATH_MAX_LEN

        # Local IPC avoids unencrypted TCP. Keep socket paths short and in a
        # private directory; TemporaryDirectory removes them after execution.
        with tempfile.TemporaryDirectory(prefix="qnb-ipc-") as tmp:
            socket_base = f"{tmp}/kernel"
            # Reserve a hyphen and five digits for Jupyter's channel suffix.
            # Count filesystem bytes: TMPDIR can contain multibyte characters.
            if len(os.fsencode(f"{socket_base}-65535")) <= IPC_PATH_MAX_LEN:
                cmd.extend(["--KernelManager.transport=ipc", f"--KernelManager.ip={socket_base}"])
            else:
                cmd.append("--KernelManager.transport=tcp")
            run(cmd, env=env)
    else:
        run(cmd, env=env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Execute selected QUBONotebooks notebooks locally through Jupyter."
    )
    parser.add_argument(
        "--julia-project",
        type=Path,
        help="Start Julia in this project, with the shared notebooks project as kernel-tool fallback.",
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
    julia_project = args.julia_project
    if julia_project is not None:
        julia_project = (REPO_ROOT / julia_project).resolve()
        if not julia_notebooks:
            raise ValueError("--julia-project requires a Julia notebook")
        if not (julia_project / "Project.toml").is_file():
            raise FileNotFoundError(f"Julia project was not found: {julia_project}")

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
        instantiate_julia_project(julia_executable, project=JULIA_PROJECT if julia_project is not None else None)
        if julia_project is not None:
            instantiate_julia_project(julia_executable, project=julia_project)
        with tempfile.TemporaryDirectory(prefix="qubonotebooks-jupyter-kernels-") as tmp:
            kernel_name, env = julia_kernel_spec_dir(
                Path(tmp),
                julia_executable=julia_executable,
                project=julia_project,
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
