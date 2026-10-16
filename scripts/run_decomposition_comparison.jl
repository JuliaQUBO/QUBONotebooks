# Opt-in only. Root must approve the frozen plan before launching this script.
# Never retries, replaces observations, or overwrites an existing output directory.
const SCRIPT_STARTED=time_ns()
using TOML, SHA
include(joinpath(@__DIR__,"decomposition_application.jl"))
using .DecompositionApplication
const DA=DecompositionApplication
length(ARGS)==1 || error("Usage: run_decomposition_comparison.jl NEW_OUTPUT_DIRECTORY")
DA.require_released_environment()
Threads.nthreads()==1 || error("One Julia thread required")
output=abspath(only(ARGS))
ispath(output) && error("Retain previous attempts; output directory must be new")
mkdir(output)
function save(path, data)
    payload=sprint(io->TOML.print(io,data))
    sizeof(payload)<=256*1024 || error("Text artifact exceeds frozen 256 KiB cap")
    used=sum(filesize(file) for file in readdir(output;join=true) if isfile(file);init=0)
    replacement=isfile(path) ? filesize(path) : 0
    used-replacement+sizeof(payload)<=4*1024^2-256*1024 || error("Artifact cohort exceeds cap including reserved process log")
    temporary=path*".tmp"
    write(temporary,payload)
    mv(temporary,path;force=true)
end
paths=["scripts/decomposition_application.jl","scripts/run_decomposition_comparison.jl",
    "scripts/run_decomposition_campaign.py","scripts/check_decomposition_release_gate.py",
    "notebooks_data/decomposition_platform.toml",
    ["notebooks_jl/environments/12-Decomposition/"*name for name in
        ("Project.toml","Manifest.toml","Manifest-v1.12.toml","RELEASE-GATES.toml")]...]
input_hashes=Dict(path=>bytes2hex(sha256(read(joinpath(DA.ROOT,path)))) for path in paths)
# Symmetric warmups, then rotate method order across the three measured rounds.
schedule=[(method=method,repetition=0) for method in DA.METHODS]
for repetition in 1:3, offset in 0:3
    push!(schedule,(method=DA.METHODS[mod1(offset+repetition,4)],repetition=repetition))
end
plan=Dict("source_head"=>readchomp(`git -C $(DA.ROOT) rev-parse HEAD`),
    "julia_version"=>string(VERSION),"input_hashes"=>input_hashes,
    "campaign_top_level_attempts"=>16,"warmups_per_method"=>1,"measured_per_method"=>3,
    "source_dimension"=>49,"maximum_compiled_dimension"=>49,"composite_child_limit"=>6,
    "exact_assignment_reservation"=>4096,"attempt_end_to_end_seconds"=>30,
    "whole_command_timeout_seconds"=>600,"hard_address_space_bytes"=>8589934592,
    "julia_threads"=>1,"blas_threads"=>1,"retries"=>0,"replacement_attempts"=>0,
    "compiler_search_dispatches"=>0,"iterative_penalty_refinements"=>0,
    "start_policy"=>"No explicit solver warm start; composite uses zero input; GLPK initialization is internal",
    "schedule"=>[Dict("method"=>string(row.method),"repetition"=>row.repetition) for row in schedule])
save(joinpath(output,"plan.toml"),plan) # freeze before the first compile/solve
isempty(readchomp(`git -C $(DA.ROOT) status --porcelain -uall`)) || error("Commit reviewed sources before execution")
ledger=DA.Ledger(max_attempts=16,max_assignments=4096,max_child_calls=240,max_parent_evaluations=15148)
process_started=time_ns()
rows=Dict{String,Any}[]
for (attempt,entry) in enumerate(schedule)
    path=joinpath(output,"attempt-$(lpad(attempt,2,'0')).toml")
    row=Dict{String,Any}("attempt"=>attempt,"method"=>string(entry.method),
        "repetition"=>entry.repetition,"warmup"=>entry.repetition==0,"outcome"=>"started")
    save(path,row) # retain a killed attempt rather than silently dropping it
    attempt_started=time_ns()
    try
        merge!(row,DA.run_attempt(entry.method;ledger))
    catch error
        row["outcome"]="failed"
        row["error"]=sprint(showerror,error)
        row["actual_work"]="unknown after failure; full reservation remains charged"
    finally
        row["observed_attempt_wall_sec"]=(time_ns()-attempt_started)/1e9
        row["cumulative_attempts"]=ledger.attempts
        row["cumulative_reserved_exact_assignments"]=ledger.reserved_assignments
        row["cumulative_reserved_child_calls"]=ledger.reserved_child_calls
        row["cumulative_reserved_parent_evaluations"]=ledger.reserved_parent_evaluations
        row["cumulative_compiler_calls"]=ledger.compiler_calls
        row["cumulative_parent_calls"]=ledger.parent_calls
        save(path,row)
        push!(rows,row)
    end
end
save(joinpath(output,"summary.toml"),Dict("plan"=>plan,"attempts"=>rows,
    "campaign_loop_elapsed_sec"=>(time_ns()-process_started)/1e9,
    "julia_script_elapsed_sec"=>(time_ns()-SCRIPT_STARTED)/1e9,
    "timing_scope"=>"Per attempt: fresh construction, automatic compilation, solve, decode and source audit; Julia script elapsed includes imports/plan/attempt writes until final-summary construction; launcher process.log records full process elapsed including startup and final writes."))
