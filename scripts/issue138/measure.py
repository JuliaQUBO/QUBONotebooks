"""Reproducible scratch-branch measurements for issue #138; never merge this spike.

Uses a caller-owned empty work directory, separate venvs/caches, and no GPU or
service credentials. Logs and JSON evidence stay outside the tracked source.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time


BASE = "7f886c1feb79ceedff6166c97c18ba4a167bd9ea"
ROOT = Path(__file__).resolve().parents[2]


def main():
    """Measure fresh, cached, and no-op syncs, then run independent CPU probes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("work", type=Path)
    parser.add_argument("--verify-portable", action="store_true")
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    assert not list(work.iterdir()), "Use a new empty measurement directory"
    evidence = work / "evidence"
    evidence.mkdir()
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    env.pop("CONDA_PREFIX", None)
    for name in ("DWAVE_API_TOKEN", "QCI_TOKEN", "QISKIT_IBM_TOKEN"):
        env.pop(name, None)
    env.update(CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
    cache = work / "cache"
    venv = work / "cudaq-venv"
    env.update(UV_CACHE_DIR=str(cache), UV_PROJECT_ENVIRONMENT=str(venv))
    result = {
        "base": BASE,
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "uv": subprocess.check_output(["uv", "--version"], text=True).strip(),
        "omp_threads": 2,
        "disk_free_before_bytes": shutil.disk_usage(work).free,
        "measurements": {},
    }

    def run(label, cmd, *, cwd=ROOT, run_env=None, expected=0):
        started = time.perf_counter()
        with (evidence / f"{label}.log").open("w") as log:
            completed = subprocess.run(cmd, cwd=cwd, env=run_env or env,
                                       stdout=log, stderr=subprocess.STDOUT)
        measurement = {"seconds": round(time.perf_counter() - started, 3),
                       "exit_code": completed.returncode, "command": cmd}
        result["measurements"][label] = measurement
        (evidence / "results.json").write_text(json.dumps(result, indent=2) + "\n")
        print(label, json.dumps(measurement), flush=True)
        if completed.returncode != expected:
            print((evidence / f"{label}.log").read_text(), flush=True)
            raise RuntimeError(f"{label} exited {completed.returncode}, expected {expected}")

    def size(path):
        # Apparent bytes are reproducible across hardlink/copy installation modes.
        return int(subprocess.check_output(["du", "-sb", str(path)], text=True).split()[0])

    baseline = work / "baseline"
    baseline.mkdir()
    archive = subprocess.run(["git", "archive", BASE], cwd=ROOT, check=True, stdout=subprocess.PIPE).stdout
    subprocess.run(["tar", "-x", "-C", str(baseline)], input=archive, check=True)
    export = ["uv", "export", "--locked", "--group", "docs", "--group", "qubo", "--no-header"]
    for label, cwd in (("base", baseline), ("candidate", ROOT)):
        exported = subprocess.check_output(export, cwd=cwd, env=env)
        (evidence / f"portable-{label}.txt").write_bytes(exported)
    before = (evidence / "portable-base.txt").read_bytes()
    after = (evidence / "portable-candidate.txt").read_bytes()
    result["portable_export_identical"] = before == after
    result["portable_export_sha256"] = hashlib.sha256(after).hexdigest()
    assert before == after, "The optional group changed portable dependencies"
    run("lock-check", ["uv", "lock", "--check"])
    # Resolution/export has populated metadata, not wheel artifacts. Clear only
    # this new task-owned cache so 'cold' includes all package transfers.
    shutil.rmtree(cache)
    sync = ["uv", "sync", "--locked", "--python", "3.12", "--group", "docs", "--group", "qubo", "--group", "cudaq"]
    run("cudaq-cold-sync", sync)
    result["cudaq_cache_bytes"] = size(cache)
    result["cudaq_venv_bytes"] = size(venv)
    result["disk_free_after_cudaq_bytes"] = shutil.disk_usage(work).free
    run("cudaq-noop-sync", sync)
    shutil.rmtree(venv)
    run("cudaq-warm-recreate-sync", sync)
    for index in (1, 2):
        run(f"quantum-{index}", [str(venv / "bin/python"), str(ROOT / "scripts/issue138/quantum_probe.py")])
    # CUDA-Q 0.16 emits an API migration warning on import. Keep the full logs,
    # but compare the canonical result separately from host-specific log paths.
    payloads = []
    for index in (1, 2):
        lines = (evidence / f"quantum-{index}.log").read_bytes().splitlines()
        json_lines = [line for line in lines if line.startswith(b"{")]
        assert len(json_lines) == 1, "Expected one quantum result object"
        payloads.append(json_lines[0])
        (evidence / f"quantum-{index}.json").write_bytes(json_lines[0] + b"\n")
    first, second = payloads
    result["quantum_processes_byte_identical"] = first == second
    result["quantum_output_sha256"] = hashlib.sha256(first).hexdigest()
    result["quantum"] = json.loads(first)
    # Export and manifest inventory also establish that no CUDA packages enter
    # the unchanged default path; execute that path in a CUDA-free environment.
    portable_env = env | {"UV_PROJECT_ENVIRONMENT": str(work / "portable-venv")}
    portable_sync = ["uv", "sync", "--locked", "--group", "docs", "--group", "qubo"]
    run("portable-sync", portable_sync, run_env=portable_env)
    result["portable_venv_bytes"] = size(work / "portable-venv")
    result["cudaq_incremental_venv_bytes"] = result["cudaq_venv_bytes"] - result["portable_venv_bytes"]
    run("portable-no-cudaq", [str(work / "portable-venv/bin/python"), "-c",
        "import importlib.util; assert importlib.util.find_spec('cudaq') is None; print('CUDA-Q absent')"], run_env=portable_env)
    python310_env = env | {"UV_PROJECT_ENVIRONMENT": str(work / "python310-venv")}
    run("python310-cudaq-rejected", ["uv", "sync", "--locked", "--python", "3.10",
        "--no-python-downloads", "--group", "cudaq"], run_env=python310_env, expected=2)
    rejection = (evidence / "python310-cudaq-rejected.log").read_text()
    assert "tool.uv.dependency-groups.cudaq.requires-python" in rejection, rejection
    run("python310-portable-dry-run", [*portable_sync, "--python", "3.10",
        "--no-python-downloads", "--dry-run"], run_env=python310_env)
    if args.verify_portable:
        for label, cwd in (("base", baseline), ("candidate", ROOT)):
            run(f"portable-execute-{label}", ["make", "verify-python-portable", f"UV_CACHE_DIR={cache}"],
                cwd=cwd, run_env=portable_env)
        run("python-tests", ["make", "test-python", f"PYTHON={work / 'portable-venv/bin/python'}"], run_env=portable_env)
    result["disk_free_final_bytes"] = shutil.disk_usage(work).free
    (evidence / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
