# SPDX-License-Identifier: MIT
module DecompositionApplication
using JuMP, QUBODecomposition, QUBODrivers, QUBOTools, ToQUBO, HiGHS
using TOML, SHA, Pkg
import MathOptInterface as MOI

const ROOT = normpath(joinpath(@__DIR__, ".."))
const DATA = joinpath(ROOT, "notebooks_data", "decomposition_platform.toml")
const PROJECT = joinpath(ROOT, "notebooks_jl", "environments", "12-Decomposition")
const CHILD_LIMIT = 6
const PARENT_LIMIT = 49
const ATTEMPT_SECONDS = 30.0
const METHODS = (:direct_mip, :separator_mip, :partition_mip, :separator_exact)

function require_released_environment()
    gate = TOML.parsefile(joinpath(PROJECT, "RELEASE-GATES.toml"))
    gate["status"] == "ready" || error("Tutorial release/install gate is pending: " * gate["reason"])
    pkgversion(QUBODrivers) >= v"0.6.6" || error("Corrected published ExactSampler required")
    pkgversion(QUBODecomposition) == VersionNumber(gate["decomposition_version"]) ||
        error("Wrong accepted standalone decomposition release")
    for name in ("QUBODrivers", "QUBODecomposition")
        info = only(v for v in values(Pkg.dependencies()) if v.name == name)
        !info.is_tracking_path && !info.is_tracking_repo || error("Published registry dependencies required")
    end
    return nothing
end

function instance(path=DATA)
    d = TOML.parsefile(path)
    b, c = d["base"], d["platform_increment"]
    length(b) == length(c) == 8 || error("Eight fixed departments required")
    all(length(row) == 6 for row in [b; c]) || error("Six alternatives required")
    all(v isa Integer for row in [b; c] for v in row) || error("Integer synthetic points required")
    return (; b, c, cost=d["platform_cost"], departments=d["departments"], alternatives=d["alternatives"])
end

# Independent source oracle: 96 scalar option evaluations, not a QUBO solver.
function source_reference(d)
    scores = [[[d.b[g][i]+y*d.c[g][i] for i in 1:6] for g in 1:8] for y in 0:1]
    choices = [[argmax(row) for row in branch] for branch in scores]
    values = [sum(maximum,row)-d.cost*y for (y,row) in zip(0:1,scores)]
    y = argmax(values) - 1
    return (; values, optimum=maximum(values), platform=y, choices=choices[y+1])
end

function source_audit(d, decoded, xids, yid)
    required = Set([vec(xids); yid])
    Set(keys(decoded)) == required || error("Incomplete or extraneous decoded source assignment")
    x = [decoded[xids[g,i]] for g in 1:8, i in 1:6]
    y = decoded[yid]
    all(v isa Real && isfinite(v) && v in (0,1) for v in [vec(x); y]) ||
        error("Decoded source variable violates its binary domain")
    residuals = [sum(x[g,i] for i in 1:6)-1 for g in 1:8]
    objective = sum((d.b[g][i]+d.c[g][i]*y)*x[g,i] for g in 1:8, i in 1:6)-d.cost*y
    feasible = all(iszero, residuals)
    reference = source_reference(d)
    gap = feasible ? reference.optimum-objective : nothing
    feasible && gap < 0 && error("Source value exceeds independent optimum")
    return (; x, y, residuals, objective, feasible, gap, reference)
end

# The bound is checked before exponentiation; this is only a CHILD guard.
function exact_assignments(n::Integer)
    !(n isa Bool) && 0 <= n <= CHILD_LIMIT || throw(ArgumentError("ExactSampler child must have 0–6 logical variables"))
    return 1 << n
end

function original_energy(source, bits)
    vars = MOI.get(source, MOI.ListOfVariableIndices())
    length(vars) == length(bits) || error("Incomplete target assignment")
    state = Dict(zip(vars,bits))
    ft = MOI.get(source, MOI.ObjectiveFunctionType())
    f = MOI.get(source, MOI.ObjectiveFunction{ft}())
    f isa MOI.ScalarQuadraticFunction || error("Expected a quadratic compiled objective")
    return f.constant + sum(t.coefficient*state[t.variable] for t in f.affine_terms; init=0.0) +
        sum(t.coefficient*state[t.variable_1]*state[t.variable_2]/(t.variable_1==t.variable_2 ? 2 : 1)
            for t in f.quadratic_terms; init=0.0)
end

# Independent coefficient identity for f + sum(p_g*(sum(x_g)-1)^2).
# This compares stored monomials before solving, not conditioner coefficients.
function audit_compiled_polynomial(d,target,groups,platform,penalties)
    MOI.get(target,MOI.ObjectiveSense())==MOI.MAX_SENSE || error("Unexpected target sense")
    vars=MOI.get(target,MOI.ListOfVariableIndices())
    f=MOI.get(target,MOI.ObjectiveFunction{MOI.ScalarQuadraticFunction{Float64}}())
    actual_linear=Dict(v=>0.0 for v in vars)
    actual_pairs=Dict{Tuple{Int,Int},Float64}()
    pair(a,b)=minmax(a.value,b.value)
    for term in f.affine_terms
        actual_linear[term.variable]+=term.coefficient
    end
    for term in f.quadratic_terms
        a,b=term.variable_1,term.variable_2
        if a==b
            actual_linear[a]+=term.coefficient/2 # MOI's diagonal convention; binary a^2=a
        else
            key=pair(a,b)
            actual_pairs[key]=get(actual_pairs,key,0.0)+term.coefficient
        end
    end
    expected_linear=Dict(v=>0.0 for v in vars)
    expected_linear[platform]=-d.cost
    expected_pairs=Dict{Tuple{Int,Int},Float64}()
    for g in 1:8, i in 1:6
        expected_linear[groups[g][i]]=d.b[g][i]-penalties[g]
        expected_pairs[pair(groups[g][i],platform)]=d.c[g][i]
    end
    for g in 1:8, i in 1:5, j in i+1:6
        expected_pairs[pair(groups[g][i],groups[g][j])]=2penalties[g]
    end
    close(a,b)=isapprox(a,b;atol=1e-8,rtol=1e-12)
    close(f.constant,sum(penalties)) || error("Compiled constant/source penalty identity failed")
    all(close(actual_linear[v],expected_linear[v]) for v in vars) || error("Compiled linear/source identity failed")
    all(close(get(actual_pairs,k,0.0),get(expected_pairs,k,0.0)) for k in union(keys(actual_pairs),keys(expected_pairs))) ||
        error("Compiled quadratic/source identity failed")
    return nothing
end

function compile_application(d)
    # Public compiler-only path: automatic penalties; no installed search solver.
    compiler = ToQUBO.Optimizer()
    model = Model(() -> compiler)
    @variable(model, x[1:8,1:6], Bin)
    @variable(model, y, Bin)
    @objective(model, Max, sum((d.b[g][i]+d.c[g][i]*y)*x[g,i] for g in 1:8, i in 1:6)-d.cost*y)
    constraints = @constraint(model, [g=1:8], sum(x[g,i] for i in 1:6)==1)
    optimize!(model) # compiles; does not produce source JuMP primal/status evidence
    target = MOI.get(compiler, ToQUBO.Attributes.TargetModel())
    vars = MOI.get(target, MOI.ListOfVariableIndices())
    length(vars) == PARENT_LIMIT || error("Unexpected compiler dimension; refuse before solver dispatch")
    isempty(ToQUBO.auxiliary_variables(compiler)) || error("Unexpected slack/quadratization variables")
    xids, yid = index.(x), index(y)
    metadata = ToQUBO.reformulation_metadata(compiler)
    entries = Dict(e["id"] => e for e in metadata["original_variables"])
    Set(keys(entries)) == Set(v.value for v in [vec(xids); yid]) || error("Source ownership mismatch")
    function target_bit(v)
        entry = entries[v.value]
        length(entry["target_variables"]) == 1 || error("Native binary encoding grew")
        target_id = only(entry["target_variables"])
        terms = filter(t -> !iszero(t["coefficient"]), entry["expansion_terms"])
        length(terms)==1 && only(terms)["variables"]==[target_id] && only(terms)["coefficient"]==1 ||
            error("Expected public identity expansion for a native source binary")
        bit = MOI.VariableIndex(target_id)
        bit in vars || error("Mapping references absent target variable")
        return bit
    end
    groups = [[target_bit(xids[g,i]) for i in 1:6] for g in 1:8]
    platform = target_bit(yid)
    Set([reduce(vcat,groups); platform]) == Set(vars) || error("Target coverage mismatch")
    # Inspect the actual compiled interaction graph using the MOI polynomial.
    owner = Dict(v => g for (g,group) in enumerate(groups) for v in group)
    f = MOI.get(target, MOI.ObjectiveFunction{MOI.ScalarQuadraticFunction{Float64}}())
    adjacency = Dict(v=>Set{MOI.VariableIndex}() for v in vars if v != platform)
    for t in f.quadratic_terms
        a,b = t.variable_1,t.variable_2
        iszero(t.coefficient) || a==b || a==platform || b==platform || begin
            owner[a] == owner[b] || error("Unexpected cross-department edge")
            push!(adjacency[a],b);push!(adjacency[b],a)
        end
    end
    for group in groups
        reached=Set([first(group)]); queue=[first(group)]
        while !isempty(queue)
            v=pop!(queue)
            for w in adjacency[v]
                w in reached || (push!(reached,w);push!(queue,w))
            end
        end
        reached == Set(group) || error("Actual residual topology differs from eight six-bit groups")
        exact_assignments(length(group)) # before any factory or enumeration
    end
    penalties = [MOI.get(compiler,ToQUBO.Attributes.AppliedPenalty(),index(c)) for c in constraints]
    all(p isa Real && isfinite(p) && p<0 for p in penalties) || error("Unexpected automatic maximization penalty")
    audit_compiled_polynomial(d,target,groups,platform,penalties)
    return (; compiler, model, target, vars, xids, yid, groups, platform, penalties)
end

function method_limits(method)
    method in METHODS || throw(ArgumentError("Unknown comparison method"))
    calls = method==:direct_mip ? 1 : method==:partition_mip ? 27 : 16
    evaluations = method==:direct_mip ? 0 : method==:partition_mip ? 1+27*64 : 1+4+16*64
    assignments = method==:separator_exact ? 16*exact_assignments(CHILD_LIMIT) : 0
    return (; calls, evaluations, assignments, max_child=method==:direct_mip ? PARENT_LIMIT : CHILD_LIMIT)
end

mutable struct Ledger
    max_attempts::Int
    max_assignments::Int
    max_child_calls::Int
    max_parent_evaluations::Int
    attempts::Int
    reserved_assignments::Int
    reserved_child_calls::Int
    reserved_parent_evaluations::Int
    compiler_calls::Int
    parent_calls::Int
end
Ledger(; max_attempts=1,max_assignments=1024,max_child_calls=27,max_parent_evaluations=1729) =
    Ledger(max_attempts,max_assignments,max_child_calls,max_parent_evaluations,0,0,0,0,0,0)
function reserve!(ledger, method)
    limits=method_limits(method)
    ledger.attempts < ledger.max_attempts || error("Top-level attempt budget exhausted")
    ledger.reserved_assignments+limits.assignments <= ledger.max_assignments || error("Assignment reservation exhausted")
    ledger.reserved_child_calls+limits.calls <= ledger.max_child_calls || error("Child-call reservation exhausted")
    ledger.reserved_parent_evaluations+limits.evaluations <= ledger.max_parent_evaluations || error("Parent-evaluation reservation exhausted")
    ledger.attempts+=1
    ledger.reserved_assignments+=limits.assignments
    ledger.reserved_child_calls+=limits.calls
    ledger.reserved_parent_evaluations+=limits.evaluations
    return limits
end

function mip_child()
    child=QUBODrivers.MIPSampler.Optimizer()
    backend=MOI.OptimizerWithAttributes(HiGHS.Optimizer,
        MOI.Silent()=>true, MOI.NumberOfThreads()=>1,
        MOI.RawOptimizerAttribute("mip_rel_gap")=>0.0,
        MOI.RawOptimizerAttribute("mip_abs_gap")=>0.0)
    MOI.set(child,QUBODrivers.MIPSampler.MIPOptimizer(),backend)
    return child
end

function run_attempt(method; ledger=Ledger(), seconds=ATTEMPT_SECONDS)
    require_released_environment()
    0 < seconds <= ATTEMPT_SECONDS || throw(ArgumentError("Attempt deadline exceeds frozen cap"))
    limits=reserve!(ledger,method) # reserve failures too, before compile/dispatch
    started=time_ns(); deadline=started/1e9+seconds
    remaining()=begin
        left=deadline-time_ns()/1e9
        left>0 || error("End-to-end deadline exhausted")
        left
    end
    t=time_ns(); d=instance(); ledger.compiler_calls+=1
    compiled=compile_application(d)
    construction_compile_sec=(time_ns()-t)/1e9
    remaining()
    t=time_ns()
    children=Any[]
    factory=()->begin
        length(children)<limits.calls || error("Child factory reservation exceeded")
        child=method==:separator_exact ? QUBODrivers.ExactSampler.Optimizer() : mip_child()
        push!(children,child)
        child
    end
    optimizer = if method==:direct_mip
        factory()
    else
        QUBODecomposition.Optimizer(child_optimizer=factory,max_variables=CHILD_LIMIT,
            strategy=method==:partition_mip ? :components_then_sweeps : :separator,
            max_child_calls=limits.calls,max_candidate_evaluations=limits.evaluations,
            max_separator_size=1,max_sweeps=3,stagnation_sweeps=1,seed=41)
    end
    map=MOI.copy_to(optimizer,compiled.target)
    if method != :direct_mip
        labels=collect(QUBOTools.variables(optimizer))
        position=Dict(v=>i for (i,v) in enumerate(labels))
        groups=[[position[map[v]] for v in group] for group in compiled.groups]
        separator=[position[map[compiled.platform]]]
        if method==:partition_mip
            MOI.set(optimizer,MOI.RawOptimizerAttribute("selection"),:partition)
            MOI.set(optimizer,MOI.RawOptimizerAttribute("partition_plan"),[groups; [separator]])
        else
            MOI.set(optimizer,MOI.RawOptimizerAttribute("separator"),separator)
        end
    end
    MOI.set(optimizer,MOI.TimeLimitSec(),remaining())
    ledger.parent_calls+=1
    MOI.optimize!(optimizer)
    copy_solve_sec=(time_ns()-t)/1e9
    t=time_ns()
    MOI.get(optimizer,MOI.ResultCount())>0 || error("No candidate returned")
    bits=[MOI.get(optimizer,MOI.VariablePrimal(),map[v]) for v in compiled.vars]
    all(v in (0,1) for v in bits) || error("Invalid compiled binary assignment")
    decoded=ToQUBO.project_original_state(compiled.compiler,Dict(zip(compiled.vars,bits)))
    audit=source_audit(d,decoded,compiled.xids,compiled.yid)
    energy=original_energy(compiled.target,bits)
    isapprox(MOI.get(optimizer,MOI.ObjectiveValue()),energy;atol=1e-8,rtol=1e-12) || error("Compiled energy audit failed")
    expected= audit.objective+sum(p*r^2 for (p,r) in zip(compiled.penalties,audit.residuals))
    isapprox(energy,expected;atol=1e-8,rtol=1e-12) || error("Automatic penalty/source polynomial identity failed")
    data=method==:direct_mip ? nothing : QUBOTools.metadata(QUBOTools.solution(optimizer))["decomposition"]
    status=MOI.get(optimizer,MOI.TerminationStatus())
    proof=method==:direct_mip ? status==MOI.OPTIMAL : method==:partition_mip ? false : data["separator"]["proof_complete"]
    if method==:partition_mip
        status!=MOI.OPTIMAL || error("Heuristic outer search acquired a global certificate")
        !data["separable_proof"] || error("Coupled parent was declared separable")
    end
    child_dimensions=[MOI.get(child,MOI.NumberOfVariables()) for child in children]
    all(n<=limits.max_child for n in child_dimensions) || error("Child dimension bound violated")
    actual_assignments=method==:separator_exact ?
        sum(get(QUBOTools.metadata(QUBOTools.solution(child)),"optimizer",Dict())["evaluations"] for child in children; init=0) : nothing
    actual_assignments===nothing || actual_assignments<=limits.assignments || error("Exact reservation exceeded")
    data===nothing || (data["attempted_calls"]<=limits.calls && data["candidate_evaluations"]<=limits.evaluations) || error("Shared parent cap exceeded")
    decode_audit_sec=(time_ns()-t)/1e9
    total_sec=(time_ns()-started)/1e9
    outcome = total_sec>seconds ? "deadline_overrun" : !audit.feasible ? "source_infeasible" :
        status in (MOI.OPTIMAL,MOI.LOCALLY_SOLVED) ? "complete" :
        status in (MOI.TIME_LIMIT,MOI.ITERATION_LIMIT,MOI.INTERRUPTED) ? "limited" : "failed_status"
    result_started=time_ns()
    row=Dict{String,Any}(
        "method"=>string(method),"outcome"=>outcome,"source_dimension"=>49,"compiled_dimension"=>length(bits),
        "child_limit"=>limits.max_child,"maximum_actual_child_dimension"=>maximum(child_dimensions;init=0),
        "source_objective"=>audit.objective,"compiled_objective"=>energy,"source_optimum"=>audit.reference.optimum,
        "source_feasible"=>audit.feasible,"source_gap"=>something(audit.gap,"unavailable: infeasible"),
        "source_platform"=>audit.y,"source_choices"=>[findall(==(1),audit.x[g,:]) for g in 1:8],
        "source_residuals"=>audit.residuals,"automatic_penalties"=>compiled.penalties,
        "public_status"=>string(status),"logical_global_proof"=>proof,
        "child_public_statuses"=>[string(MOI.get(child,MOI.TerminationStatus())) for child in children],
        "backend_binary_upper_bound"=>(method==:direct_mip ? 217 : method==:separator_exact ? 6 : 21),
        "completed_branches"=>data===nothing || method==:partition_mip ? "not_applicable" : data["separator"]["completed_branches"],
        "required_branches"=>data===nothing || method==:partition_mip ? "not_applicable" : data["separator"]["required_branches"],
        "attempted_child_calls"=>length(children),"completed_child_calls"=>data===nothing ? 1 : data["completed_calls"],
        "reserved_child_calls"=>limits.calls,"reserved_parent_evaluations"=>limits.evaluations,
        "parent_evaluations"=>data===nothing ? "not_applicable" : data["candidate_evaluations"],
        "reserved_exact_assignments"=>limits.assignments,"actual_exact_assignments"=>something(actual_assignments,"not_applicable"),
        "mip_search_nodes"=>"not reported by this public sampler path; not equated to exhaustive assignments",
        "construction_compile_sec"=>construction_compile_sec,"copy_solve_sec"=>copy_solve_sec,
        "decode_audit_sec"=>decode_audit_sec,"end_to_end_sec"=>total_sec,
        "compiler_search_dispatches"=>0,"iterative_penalty_refinements"=>0,
        "start_handling"=>method==:separator_exact ?
            "Composite starts at zero; ExactSampler enumerates every child assignment" :
            method==:direct_mip ? "No explicit warm start; HiGHS initializes internally" :
            "Composite starts at zero; no explicit child warm start; HiGHS initializes internally")
    row["result_construction_sec"]=(time_ns()-result_started)/1e9
    row["reported_compilation_sec"]=MOI.get(compiled.compiler,ToQUBO.Attributes.CompilationTime())
    row["end_to_end_sec"]=(time_ns()-started)/1e9
    row["end_to_end_sec"]>seconds && (row["outcome"]="deadline_overrun")
    return row
end

function correctness_demo()
    row=run_attempt(:separator_exact)
    row["outcome"]=="complete" && row["public_status"]=="OPTIMAL" && row["logical_global_proof"] ||
        error("Completed exact separator certificate required")
    row["source_feasible"] && iszero(row["source_gap"]) || error("Source optimum not independently verified")
    row["completed_branches"]==row["required_branches"]==2 || error("Incomplete coverage")
    return row
end

function comparison_report(path=joinpath(ROOT,"notebooks_data","decomposition_comparison","summary.toml"))
    isfile(path) || return nothing
    report=TOML.parsefile(path)
    plan=report["plan"]
    for (relative,expected) in plan["input_hashes"]
        bytes2hex(sha256(read(joinpath(ROOT,relative))))==expected || error("Stale comparison evidence: "*relative)
    end
    rows=report["attempts"]
    length(rows)==16 && sort([r["attempt"] for r in rows])==collect(1:16) || error("Incomplete retained attempt cohort")
    for method in string.(METHODS)
        cohort=filter(r->r["method"]==method,rows)
        sort([r["repetition"] for r in cohort])==[0,1,2,3] || error("Missing/duplicated repetition")
    end
    return report
end

struct ReportTable
    content::String
end
Base.show(io::IO,::MIME"text/markdown",table::ReportTable)=print(io,table.content)
Base.show(io::IO,::MIME"text/plain",table::ReportTable)=print(io,table.content)
function comparison_tables(report)
    rows=filter(r->!r["warmup"],report["attempts"])
    quality="| Method / repetition | Outcome | Compiled / source value | Source reference / gap | Source feasible | Public status | Logical proof |\n| --- | --- | --- | --- | --- | --- | --- |\n"
    cost="| Method / repetition | Parent / max child | Calls | Exact assignments (reserved / observed) | Parent evaluations | Build + compile / copy + solve / decode + audit / result construction / complete attempt seconds |\n| --- | --- | --- | --- | --- | --- |\n"
    for r in rows
        label="$(r["method"]) / $(r["repetition"])"
        if !haskey(r,"end_to_end_sec")
            quality*="| $label | $(r["outcome"]) | unavailable | unavailable | unavailable | unavailable | false |\n"
            cost*="| $label | unavailable | unavailable | charged; see raw attempt | unavailable | observed failed attempt: $(r["observed_attempt_wall_sec"]) |\n"
            continue
        end
        quality*="| $label | $(r["outcome"]) | $(r["compiled_objective"]) / $(r["source_objective"]) | $(r["source_optimum"]) / $(r["source_gap"]) | $(r["source_feasible"]) | $(r["public_status"]) | $(r["logical_global_proof"]) |\n"
        times=join([round(r[key];digits=6) for key in ("construction_compile_sec","copy_solve_sec","decode_audit_sec","result_construction_sec","observed_attempt_wall_sec")]," / ")
        cost*="| $label | $(r["compiled_dimension"]) / $(r["maximum_actual_child_dimension"]) | $(r["attempted_child_calls"]) | $(r["reserved_exact_assignments"]) / $(r["actual_exact_assignments"]) | $(r["parent_evaluations"]) | $times |\n"
    end
    return ReportTable(quality),ReportTable(cost)
end

end
