#!/usr/bin/env python3
"""Execute the decomposition lesson's numerical cells and additional guard probes."""

import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "notebooks_jl/12-Decomposition.ipynb"
PROJECT = ROOT / "notebooks_jl/environments/12-Decomposition"


def main():
    notebook = json.loads(NOTEBOOK.read_text())
    cells = [
        cell for cell in notebook["cells"]
        if cell["cell_type"] == "code"
        and "installation" not in cell.get("metadata", {}).get("tags", [])
        and not cell.get("metadata", {}).get("qubonotebooks_colab_import_id")
    ]
    with tempfile.TemporaryDirectory(prefix="decomposition-tests-") as temporary:
        directory = Path(temporary)
        sources = []
        for i, cell in enumerate(cells):
            path = directory / f"{i}.jl"
            path.write_text("".join(cell["source"]))
            sources.append(str(path))
        runner = directory / "run.jl"
        runner.write_text('''using Test, REPL
using JuMP, QUBODecomposition, QUBODrivers, QUBOTools, ToQUBO
import MathOptInterface as MOI
for path in ARGS
    include_string(REPL.softscope, Main, read(path, String), path)
end
@testset "Decomposition numerical and guard regressions" begin
    # Defect class: a logical/compiled dimension is checked after allocation or dispatch.
    @test_throws ArgumentError binary_states(9)
    @test_throws ArgumentError binary_states(-1)
    @test_throws ArgumentError binary_states(typemax(Int))
    @test_throws ArgumentError qubo_model(zeros(9), [])
    @test_throws ArgumentError tiny_solve(model_a; capacity=9)
    oversized = MOI.Utilities.Model{Float64}()
    MOI.add_variables(oversized, 9)
    @test_throws ArgumentError tiny_solve(oversized; strategy=:direct)
    @test length(binary_states(8)) == 256
    @test binary_states(0) == [Int[]]
    # Defect class: missing boundary terms or duplicated constants survive a solver-only check.
    @test components_a.bits == [1,0,0,1]
    @test components_a.energy == 0
    @test separator_b.bits == ones(Int,5)
    @test separator_b.energy == 0
    @test separator_b.data["candidate_evaluations"] == 21
    @test separator_b.data["completed_calls"] == 4
    @test all(call["valid_results"] == 4 for call in separator_b.data["calls"])
    @test Set(call["boundary_fixed_variables"][3] for call in separator_b.data["calls"]) == Set((0,1))
    @test sweeps_c.energy - oracle_c == 24
    @test all(call["public_status"] == "LOCALLY_SOLVED" for call in sweeps_c.data["calls"])
    # Defect class: a globally best compiled state is presented as source feasible.
    @test weak_d.decoded == [1,1]
    @test weak_d.residual == 1 && !weak_d.source_feasible
    @test weak_d.result.energy ≈ 9.9
    @test strong_d.decoded == [1,0]
    @test strong_d.residual == 0 && strong_d.source_feasible
    @test strong_d.source_objective == 8
    @test all(!row[2].data["separator"]["proof_complete"] for row in comparison_rows if row[2].data !== nothing && row[2].data["separator"] !== nothing)
    # Defect class: exhausted allowances accidentally retain an exact-route proof.
    @test limited_b.status == MOI.ITERATION_LIMIT
    @test limited_b.data["completed_calls"] == 1
    truncated = tiny_solve(model_b; strategy=:separator, separator=[3], candidates=2)
    @test truncated.status == MOI.ITERATION_LIMIT
    @test truncated.data["candidate_evaluations"] == 2
    @test truncated.data["attempted_calls"] == 0
    @test truncated.data["separator"]["completed_branches"] == 0
    @test truncated.energy == energy_b(truncated.bits)
end
''')
        command = [os.environ.get("JULIA_BIN", "julia"), "--startup-file=no", f"--project={PROJECT}", str(runner), *sources]
        subprocess.run(command, cwd=ROOT, check=True, timeout=180)


if __name__ == "__main__":
    main()
