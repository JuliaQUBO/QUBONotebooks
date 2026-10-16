#!/usr/bin/env python3
"""Opt-in Linux launcher for the separately approved 16-attempt CPU campaign."""
import argparse
import os
from pathlib import Path
import resource
import selectors
import signal
import subprocess
import time

from check_decomposition_release_gate import readiness_errors

ROOT = Path(__file__).resolve().parents[1]
LOG_LIMIT = 256 * 1024
HARD_AS = 8 * 1024**3


def _signal_owned_group(process, signum):
    # Every caller created this exact group with start_new_session=True.
    try:
        os.killpg(process.pid, signum)
    except ProcessLookupError:
        pass


def _terminate_owned(process, grace):
    _signal_owned_group(process, signal.SIGTERM)
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        _signal_owned_group(process, signal.SIGKILL)
        process.wait(timeout=1)


def run_bounded(command, *, cwd, environment, log_path,
                execution_seconds=595, log_limit=LOG_LIMIT, grace=4):
    """Own one subprocess group; bounded inert tests use smaller limits."""
    if not (0 < execution_seconds <= 595 and 0 < grace <= 4 and 1024 <= log_limit <= LOG_LIMIT):
        raise ValueError("Limits exceed the frozen process allowance")

    def limits():
        resource.setrlimit(resource.RLIMIT_AS, (HARD_AS, HARD_AS))

    started = time.monotonic()
    stopped = None
    process = None
    selector = selectors.DefaultSelector()
    with log_path.open("xb") as log:
        try:
            process = subprocess.Popen(command, cwd=cwd, env=environment,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       start_new_session=True, preexec_fn=limits)
            size = 0
            if process.stdout is None:
                stopped = "missing stdout pipe"
            else:
                try:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while selector.get_map():
                        if time.monotonic() - started >= execution_seconds:
                            stopped = "execution deadline"
                            break
                        for key, _ in selector.select(timeout=0.05):
                            chunk = os.read(key.fileobj.fileno(), 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            allowed = log_limit - 512 - size
                            log.write(chunk[:max(0, allowed)])
                            size += min(len(chunk), max(0, allowed))
                            if len(chunk) > allowed:
                                stopped = "process-log byte limit"
                                break
                        if stopped:
                            break
                except (OSError, ValueError) as error:
                    stopped = "stdout monitoring failed: " + type(error).__name__
            if stopped:
                _terminate_owned(process, grace)
            else:
                remaining = max(0.01, execution_seconds - (time.monotonic() - started))
                try:
                    process.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    stopped = "execution deadline after stdout closed"
                    _terminate_owned(process, grace)
        finally:
            selector.close()
            if process is not None:
                if process.poll() is None:
                    _terminate_owned(process, grace)
                # No reusable services belong to this one-shot campaign. Drain
                # only this owned group, including descendants after parent exit.
                _signal_owned_group(process, signal.SIGKILL)
                if process.stdout is not None:
                    process.stdout.close()
                elapsed = time.monotonic() - started
                log.write(f"\nLauncher exit={process.returncode}, stopped={stopped}, elapsed={elapsed:.6f}s including process startup/imports/artifacts; no retries.\n".encode())
    return {"returncode": process.returncode, "stopped": stopped,
            "elapsed_sec": time.monotonic() - started}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--julia", required=True, help="Absolute reviewed Julia 1.10.11 executable")
    parser.add_argument("--depot", required=True, help="Owned writable first depot; explicit read-only caches may follow")
    parser.add_argument("--output", required=True, type=Path, help="New campaign artifact directory")
    args = parser.parse_args()
    errors = readiness_errors()
    if errors:
        raise SystemExit("Release/install gate pending: " + "; ".join(errors))
    if not Path(args.julia).is_absolute():
        raise SystemExit("Absolute Julia executable required")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    environment = os.environ.copy()
    environment.update(JULIA_DEPOT_PATH=args.depot, JULIA_LOAD_PATH="@:@stdlib",
                       JULIA_NUM_THREADS="1", JULIA_NUM_PRECOMPILE_TASKS="1",
                       JULIA_PKG_PRECOMPILE_AUTO="0", JULIA_PKG_OFFLINE="true",
                       OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    command = [args.julia, "--startup-file=no",
               f"--project={ROOT / 'notebooks_jl/environments/12-Decomposition'}",
               str(ROOT / "scripts/run_decomposition_comparison.jl"), str(output / "records")]
    result = run_bounded(command, cwd=ROOT, environment=environment,
                         log_path=output / "process.log")
    print(f"Campaign {result}")
    raise SystemExit(1 if result["stopped"] else result["returncode"])


if __name__ == "__main__":
    main()
