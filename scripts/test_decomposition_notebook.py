#!/usr/bin/env python3
"""Pure guard/source-oracle checks; no extra large tutorial optimizer solves."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "notebooks_jl/environments/12-Decomposition"


def main():
    subprocess.run([os.environ.get("PYTHON", "python3"), str(ROOT / "scripts/check_decomposition_release_gate.py")], check=True)
    with tempfile.TemporaryDirectory(prefix="decomposition-guards-") as temporary:
        runner = Path(temporary) / "run.jl"
        runner.write_text('''using Test
include(ARGS[1])
const DA=DecompositionApplication
@testset "Department/platform independent source and pre-dispatch guards" begin
    data=DA.instance()
    reference=DA.source_reference(data)
    @test reference.values==[205,259]
    @test reference.platform==1
    @test reference.choices==fill(6,8)
    @test DA.exact_assignments(6)==64
    for n in (-1,7,49,typemax(Int),true)
        @test_throws ArgumentError DA.exact_assignments(n)
    end
    xids=reshape(collect(1:48),8,6);yid=49
    decoded=Dict(id=>Int(i==6) for (g,i,id) in ((g,i,xids[g,i]) for g in 1:8 for i in 1:6))
    decoded[yid]=1
    audit=DA.source_audit(data,decoded,xids,yid)
    @test audit.feasible && audit.objective==259 && audit.gap==0
    @test_throws ErrorException DA.source_audit(data,filter(p->first(p)!=yid,decoded),xids,yid)
    bad=copy(decoded);bad[xids[1,1]]=1
    @test !DA.source_audit(data,bad,xids,yid).feasible
    fractional=Dict{Int,Float64}(bad);fractional[xids[1,1]]=0.5
    @test_throws ErrorException DA.source_audit(data,fractional,xids,yid)
    # The application itself has a block-coordinate trap at the y=0 source optimum.
    @test all(argmax(data.b[g])==1 for g in 1:8)
    @test all(iszero(data.c[g][1]) for g in 1:8)
    @test data.cost>0 # platform flip alone reduces value; departments already maximize at y=0
    ledger=DA.Ledger(max_attempts=1,max_assignments=1024)
    @test DA.reserve!(ledger,:separator_exact).assignments==1024
    @test_throws ErrorException DA.reserve!(ledger,:separator_exact)
    @test ledger.reserved_assignments==1024 # refused work cannot erase prior reservations
    @test ledger.compiler_calls==ledger.parent_calls==0
    @test DA.method_limits(:separator_exact).evaluations==1029
    @test DA.method_limits(:partition_mip).calls==27
    @test_throws ArgumentError DA.method_limits(:unknown)
end
''')
        subprocess.run([os.environ.get("JULIA_BIN", "julia"), "--startup-file=no", f"--project={PROJECT}", str(runner), str(ROOT / "scripts/decomposition_application.jl")], cwd=ROOT, check=True, timeout=180)


if __name__ == "__main__":
    main()
