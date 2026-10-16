#!/usr/bin/env python3
"""Execute the real LP/MIP cells of Julia notebooks 1 and 2 without cloud/plots.

Two isolated Julia processes use the focused locks. The fixed fixtures make four
optimizer calls (one LP, two linearized MIPs, one 11-spin ExactSampler reference)
and two independent 2^11 objective scans. Nothing is written to the notebooks.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]


def source_cell(notebook: str, marker: str) -> str:
    path = REPO_ROOT / "notebooks_jl" / f"{notebook}.ipynb"
    cells = json.loads(path.read_text())["cells"]
    matches = ["".join(c["source"]) for c in cells
               if c["cell_type"] == "code" and marker in "".join(c["source"])]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {marker!r} cell in {path}")
    return matches[0]


def fixture(notebook: str) -> str:
    def cell(marker: str) -> str:
        # include_string retains each selected cell exactly, including assertions.
        source = source_cell(notebook, marker)
        # Julia raw strings preserve backslashes; selected sources contain no triple quotes.
        if '"""' in source:
            raise ValueError("Selected cell requires an explicit Julia string encoding")
        return f'include_string(Main, raw"""{source}""", "{notebook}: {marker}")\n'

    prefix = "using Pkg; Pkg.instantiate(; allow_autoprecomp=false)\nusing Test, JuMP, HiGHS, LinearAlgebra\n"
    if notebook == "1-MathProg":
        return prefix + cell("lp_model = Model()") + cell("set_optimizer(lp_model, HiGHS.Optimizer)") + '''
@testset "notebook 1 HiGHS LP" begin
    @test termination_status(lp_model) == MOI.OPTIMAL
    @test all(isfinite, lp_x)
    @test all(lp_x .>= -1e-6)
    @test lp_x[2] <= lp_x[1] + 2 + 1e-6
    @test 8lp_x[1] + 2lp_x[2] <= 17 + 1e-6
    @test isapprox(5.5lp_x[1] + 2.1lp_x[2], 14.08; atol=1e-6)
    @test isapprox(objective_value(lp_model), 14.08; atol=1e-6)
    @test get_optimizer_attribute(lp_model, "threads") == 1
end
'''
    if notebook != "2-QUBO":
        raise ValueError(f"Unknown fixture {notebook}")
    return prefix + "using QUBO\n" + "".join(cell(m) for m in (
        "A = [", "ρ = sum(abs, c)", "qubo_ilp_model = Model()",
        "set_optimizer(qubo_ilp_model,",
    )) + '''
@testset "notebook 2 HiGHS QUBO linearization" begin
    @test length(qubo_ilp_x) == 11
    @test termination_status(qubo_ilp_model) == MOI.OPTIMAL
    @test all(abs.(value.(x_qubo_ilp) .- qubo_ilp_x) .<= 1e-6)
    @test all(v -> v in (0, 1), qubo_ilp_x)
    @test A * qubo_ilp_x == b
    oracle = minimum(begin
        bits = [(mask >> (i-1)) & 1 for i in 1:11]
        bits' * Q * bits + β
    end for mask in 0:(2^11-1))
    @test isapprox(qubo_ilp_x' * Q * qubo_ilp_x + β, oracle; atol=1e-6)
    @test isapprox(objective_value(qubo_ilp_model), oracle; atol=1e-6)
    @test all(isapprox(value(y[i,j]), qubo_ilp_x[i]*qubo_ilp_x[j]; atol=1e-6)
              for i in 1:11 for j in 1:11 if i != j)
    @test get_optimizer_attribute(qubo_ilp_model, "threads") == 1
end
''' + "".join(cell(m) for m in (
        "h = [", "set_optimizer(ising_model,", "n, L, Q, α, β =",
        "ising_ilp_model = Model()", "set_optimizer(ising_ilp_model,",
    )) + '''
@testset "notebook 2 HiGHS Ising linearization" begin
    @test length(ising_ilp_s) == 11
    @test termination_status(ising_ilp_model) == MOI.OPTIMAL
    @test all(abs.(value.(x_ising_ilp) .- ising_ilp_x) .<= 1e-6)
    @test all(v -> v in (0, 1), ising_ilp_x)
    oracle = minimum(begin
        spins = [2*((mask >> (i-1)) & 1)-1 for i in 1:11]
        spins' * J * spins + h' * spins
    end for mask in 0:(2^11-1))
    @test isapprox(ising_ilp_s' * J * ising_ilp_s + h' * ising_ilp_s, oracle; atol=1e-6)
    @test isapprox(objective_value(ising_ilp_model), objective_value(ising_model); atol=1e-6)
    @test all(isapprox(value(y[i,j]), ising_ilp_x[i]*ising_ilp_x[j]; atol=1e-6)
              for i in 1:11 for j in 1:11 if i != j)
    @test get_optimizer_attribute(ising_ilp_model, "threads") == 1
end
'''


def run_fixture(notebook: str) -> None:
    command = shlex.split(os.environ.get("JULIA_BIN", "julia"))
    project = REPO_ROOT / "notebooks_jl" / "environments" / notebook
    env = dict(os.environ, JULIA_LOAD_PATH="@:@stdlib", JULIA_PKG_PRECOMPILE_AUTO="0",
               JULIA_NUM_THREADS="1", JULIA_NUM_PRECOMPILE_TASKS="1",
               OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1",
               IJULIA_NODEFAULTKERNEL="1")
    with tempfile.TemporaryDirectory(prefix="highs-notebook-cells-") as directory:
        script = Path(directory) / "fixture.jl"
        script.write_text(fixture(notebook))
        command += ["--startup-file=no", f"--project={project}", str(script)]
        print(f"{notebook}: + {shlex.join(command)}", flush=True)
        process = subprocess.Popen(command, cwd=REPO_ROOT, env=env, start_new_session=True)
        try:
            result = process.wait(timeout=240)
            if result:
                raise subprocess.CalledProcessError(result, command)
        finally:
            # Reap owned descendants on timeout/interruption without global process operations.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()


if __name__ == "__main__":
    for key in ("1-MathProg", "2-QUBO"):
        run_fixture(key)
