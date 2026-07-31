#!/usr/bin/env python3
"""Run Julia notebook smokes on a fresh, hosted Google Colab runtime."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SOURCE_PATH = globals().get("__file__")
REPO_ROOT = (
    Path(SOURCE_PATH).resolve().parents[1] if SOURCE_PATH is not None else Path.cwd()
)
DEFAULT_REPO_URL = "https://github.com/JuliaQUBO/QUBONotebooks.git"
HOSTED_RUNNER_ENV = "QUBONOTEBOOKS_HOSTED_COLAB_RUNNER"
REPO_REF_ENV = "QUBONOTEBOOKS_REPO_REF"
SELECTED_NOTEBOOKS_ENV = "QUBONOTEBOOKS_COLAB_NOTEBOOKS"
NATIVE_KERNEL_NAME = "julia"
FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> None:
    print("+", subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def command_output(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> str:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def git_head() -> str:
    return command_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT)


def load_smoke_module(repo_root: Path):
    module_path = repo_root / "scripts" / "verify_colab_bootstrap.py"
    spec = importlib.util.spec_from_file_location(
        "qubonotebooks_verify_colab_bootstrap",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load hosted smoke module from {module_path}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_hosted_colab(env: dict[str, str]) -> None:
    markers = ("COLAB_RELEASE_TAG", "COLAB_JUPYTER_IP")
    if not any(env.get(marker) for marker in markers):
        raise RuntimeError("The hosted verifier must run inside Google Colab.")
    if not Path("/content").is_dir():
        raise RuntimeError("The hosted Colab runtime does not provide /content.")


def native_julia_kernel(*, cwd: Path, env: dict[str, str]) -> dict:
    rendered = command_output(
        [sys.executable, "-m", "jupyter", "kernelspec", "list", "--json"],
        cwd=cwd,
        env=env,
    )
    kernelspecs = json.loads(rendered).get("kernelspecs", {})
    if NATIVE_KERNEL_NAME not in kernelspecs:
        available = ", ".join(sorted(kernelspecs)) or "<none>"
        raise RuntimeError(
            "Colab's native Julia kernelspec is unavailable; " f"found: {available}."
        )
    return kernelspecs[NATIVE_KERNEL_NAME]


def validate_native_julia_kernel(kernel: dict, julia_exe: str) -> None:
    spec = kernel.get("spec", {})
    if spec.get("language") != "julia":
        raise RuntimeError("The Colab 'julia' kernelspec does not declare Julia.")
    argv = spec.get("argv", [])
    if not argv:
        raise RuntimeError("The Colab 'julia' kernelspec has no launch command.")
    kernel_exe = shutil.which(str(argv[0])) or str(argv[0])
    if Path(kernel_exe).resolve() != Path(julia_exe).resolve():
        raise RuntimeError(
            "The Colab 'julia' kernelspec does not launch the hosted Julia "
            f"executable: {argv[0]!r} != {julia_exe!r}."
        )


def execute_native_smoke(
    smoke,
    repo_root: Path,
    notebook_path: Path,
    *,
    output_dir: Path,
    env: dict[str, str],
) -> float:
    project_key = notebook_path.stem
    smoke_name = f"hosted-colab-{project_key.lower()}-smoke.ipynb"
    smoke_notebook = output_dir / smoke_name
    executed_notebook = output_dir / f"executed-{smoke_name}"
    smoke.write_smoke_notebook(
        smoke.smoke_cell_sources(repo_root, notebook_path),
        smoke_notebook,
    )

    timeout = env.get("QUBONOTEBOOKS_NOTEBOOK_TIMEOUT", "1800")
    startup_timeout = env.get("QUBONOTEBOOKS_KERNEL_STARTUP_TIMEOUT", "300")
    started = time.monotonic()
    smoke.run(
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
            f"--ExecutePreprocessor.kernel_name={NATIVE_KERNEL_NAME}",
            f"--output={executed_notebook.name}",
            smoke_notebook.name,
        ],
        cwd=output_dir,
        env=env,
    )
    elapsed = time.monotonic() - started

    executed = json.loads(executed_notebook.read_text())
    smoke.validate_notebook_execution(executed["cells"])
    conda_environment = repo_root / "notebooks_jl" / ".CondaPkg"
    if conda_environment.exists():
        raise AssertionError(
            f"Hosted Colab smoke created a CondaPkg environment at {conda_environment}."
        )
    bootstrap_outputs = executed["cells"][0].get("outputs", [])
    rendered = smoke.validate_bootstrap_outputs(
        bootstrap_outputs,
        project_key=project_key,
    )
    print(f"Captured {project_key} bootstrap output:", flush=True)
    print(rendered.rstrip(), flush=True)
    print(f"Hosted Colab {project_key} smoke passed in {elapsed:.1f}s.", flush=True)
    return elapsed


def hosted_verify_main() -> int:
    repo_root = REPO_ROOT
    env = os.environ.copy()
    require_hosted_colab(env)
    smoke = load_smoke_module(repo_root)

    julia_exe = shutil.which("julia")
    if julia_exe is None:
        raise RuntimeError("The hosted Colab runtime does not provide Julia on PATH.")
    smoke.verify_julia_1_12([julia_exe], cwd=repo_root, env=env)
    validate_native_julia_kernel(
        native_julia_kernel(cwd=repo_root, env=env),
        julia_exe,
    )

    env["QUBONOTEBOOKS_REPO_DIR"] = str(repo_root)
    for variable in (
        "JULIA_PKG_PRECOMPILE_AUTO",
        "QUBONOTEBOOKS_PRECOMPILE",
        "QUBONOTEBOOKS_WARM_PACKAGES",
    ):
        env.pop(variable, None)

    notebook_paths = smoke.selected_notebook_paths()
    print(
        "Hosted Colab runtime: " f"{env.get('COLAB_RELEASE_TAG', '<unknown release>')}",
        flush=True,
    )
    print(f"Hosted Julia executable: {julia_exe}", flush=True)
    print(
        "Selected Julia notebooks: " + ", ".join(path.stem for path in notebook_paths),
        flush=True,
    )

    with tempfile.TemporaryDirectory(
        prefix="qubonotebooks-native-julia-",
        dir="/content",
    ) as tmp:
        total_started = time.monotonic()
        for notebook_path in notebook_paths:
            execute_native_smoke(
                smoke,
                repo_root,
                notebook_path,
                output_dir=Path(tmp),
                env=env,
            )
        total_elapsed = time.monotonic() - total_started

    print(
        "Native hosted Colab Julia smokes passed " f"in {total_elapsed:.1f}s.",
        flush=True,
    )
    return 0


def hosted_checkout_main() -> int:
    env = os.environ.copy()
    require_hosted_colab(env)
    repo_ref = env.get(REPO_REF_ENV, "").strip()
    if not repo_ref:
        raise ValueError(f"{REPO_REF_ENV} must identify the exact revision to test.")
    repo_url = env.get("QUBONOTEBOOKS_REPO_URL", DEFAULT_REPO_URL)

    with tempfile.TemporaryDirectory(
        prefix="qubonotebooks-hosted-ref-",
        dir="/content",
    ) as tmp:
        checkout = Path(tmp) / "QUBONotebooks"
        run(["git", "init", "--quiet", str(checkout)], cwd=Path("/content"))
        run(["git", "remote", "add", "origin", repo_url], cwd=checkout)
        run(
            ["git", "fetch", "--quiet", "--depth", "1", "origin", repo_ref],
            cwd=checkout,
        )
        run(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=checkout)
        actual_ref = command_output(["git", "rev-parse", "HEAD"], cwd=checkout)
        if FULL_SHA.fullmatch(repo_ref) and actual_ref.lower() != repo_ref.lower():
            raise RuntimeError(
                f"Hosted checkout mismatch: requested {repo_ref}, got {actual_ref}."
            )
        print(f"Hosted Colab checkout: {actual_ref}", flush=True)

        env[REPO_REF_ENV] = actual_ref
        env[HOSTED_RUNNER_ENV] = "verify"
        run(
            [sys.executable, str(checkout / "scripts" / "verify_hosted_colab.py")],
            cwd=checkout,
            env=env,
        )
    return 0


def colab_run_command(
    *,
    script_path: Path,
    auth: str,
    timeout: float,
    repo_ref: str,
    repo_url: str,
    notebooks: str,
) -> list[str]:
    return [
        "colab",
        "--auth",
        auth,
        "run",
        "--timeout",
        str(timeout),
        "--env",
        f"{HOSTED_RUNNER_ENV}=checkout",
        "--env",
        f"{REPO_REF_ENV}={repo_ref}",
        "--env",
        f"QUBONOTEBOOKS_REPO_URL={repo_url}",
        "--env",
        f"{SELECTED_NOTEBOOKS_ENV}={notebooks}",
        str(script_path),
    ]


def local_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--notebooks",
        default=os.environ.get(SELECTED_NOTEBOOKS_ENV, "11-Annealing"),
        help="Comma- or space-separated Julia notebook keys (default: 11-Annealing).",
    )
    parser.add_argument("--ref", default=os.environ.get(REPO_REF_ENV) or git_head())
    parser.add_argument(
        "--repo-url",
        default=os.environ.get("QUBONOTEBOOKS_REPO_URL", DEFAULT_REPO_URL),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("QUBONOTEBOOKS_COLAB_TIMEOUT", "3600")),
    )
    parser.add_argument(
        "--auth",
        default=os.environ.get("QUBONOTEBOOKS_COLAB_AUTH", "oauth2"),
    )
    args = parser.parse_args(argv)

    run(
        colab_run_command(
            script_path=Path(__file__).resolve(),
            auth=args.auth,
            timeout=args.timeout,
            repo_ref=args.ref,
            repo_url=args.repo_url,
            notebooks=args.notebooks,
        ),
        cwd=REPO_ROOT,
    )
    return 0


if __name__ == "__main__":
    hosted_phase = os.environ.get(HOSTED_RUNNER_ENV)
    if hosted_phase == "checkout":
        raise SystemExit(hosted_checkout_main())
    if hosted_phase == "verify":
        raise SystemExit(hosted_verify_main())
    raise SystemExit(local_main())
