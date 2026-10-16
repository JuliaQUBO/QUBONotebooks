# Department/platform tutorial: retained comparison and execution audit

The fixed synthetic application has 49 source binaries and a six-variable child
limit. The retained local comparison is one completed 16-attempt cohort on Julia
1.10.11: one warmup and three measured repetitions for each of four methods.
The [exact summary](../notebooks_data/decomposition_comparison/summary.toml)
retains every attempt, including warmups and deadline overruns. No retry,
replacement observation, coefficient tuning or additional grid was run.

## Formulation, source reference and certificates

Eight departments each choose one of six alternatives. The platform bit changes
option values and costs 60 annual net-value points. The objective maximizes
`sum((b[g,i]+c[g,i]*y)*x[g,i])-60y`, subject to one choice per department and binary
x/y. The displayed fixed TOML coefficients are synthetic. An independent source
oracle evaluates 96 option scores across the two platform states and obtains
branch optima 205 and 259. This oracle already solves the particular structured
source problem; it is also a transparent reference for auditing the compiled
solver results. The example is not an industrial utility or general hardness
benchmark.

Each attempt constructs a fresh source model and uses public compiler-only
`ToQUBO.Optimizer()`, default automatic penalties, `optimize!(source_model)`,
`TargetModel()`, `reformulation_metadata` and `project_original_state`. There are
no penalty hints, private state injection, refinement overrides or iterative
penalty refinements. The compiler dispatches zero search solvers. One extracted
QUBO is solved manually per attempt; no source JuMP primals/status are claimed
from the compiler-only call. Infeasible source decoding would be retained as a
failure. An attached-solver refinement path would require its own nested-work
accounting.

Before constructing a backend, the actual compiled target must contain exactly
49 variables, no auxiliaries, one identity target bit per original binary and
complete ownership/mapping coverage. Removing the platform must produce eight
connected six-variable residual components. The entire compiled polynomial is
independently compared with the source objective plus automatically applied
one-choice penalties, including constants, binary diagonals and MOI scaling.
All 16 attempts passed these checks and complete decoded source audits. The
automatic equality coefficients were -1492; they were inspected, never supplied
or overridden. Every returned source assignment was feasible and its compiled
value equaled its independently recomputed source value.

The compiled polynomial has 120 within-department pair terms and 40 nonzero
platform pair terms. In this release's MIPSampler binary-product linearization,
that implies 160 binary product auxiliaries plus 49 logical binaries for the
direct model (209 backend binaries). A six-bit department child has at most
15 product auxiliaries plus six logical binaries (21 total). Raw result records
retain conservative upper bounds of 217 direct and 21 child binaries. Backend
linearization size and logical child capacity are different quantities.

## Observed quality, capacity and complete cost

The baseline is unrestricted GLPK MIPSampler applied to the **same compiled
QUBO**, not a separately strengthened source MIP formulation. The next two
methods use the same GLPK factory/settings in complete one-bit separator
conditioning or partition sweeps. The fourth uses actual unchanged ExactSampler
children for complete separator conditioning. Composite input starts are zero;
GLPK initializes internally. No identical consumed warm-start claim is made.

| Method | Three measured source values / gaps | Public status / logical certificate | Complete measured attempt seconds |
| --- | --- | --- | --- |
| Direct GLPK on compiled QUBO | 233 / 26 each | TIME_LIMIT / none | 30.012058173, 30.035143870, 30.010748824 |
| Complete separator, GLPK | 259 / 0 each | OPTIMAL / 2 of 2 branches | 0.046128933, 0.035710003, 0.050347700 |
| Partition sweeps, GLPK | 205 / 54 each | LOCALLY_SOLVED / none | 0.041297479, 0.037211131, 0.038736455 |
| Complete separator, ExactSampler | 259 / 0 each | OPTIMAL / 2 of 2 branches | 0.066611615, 0.031006958, 0.022682710 |

All four direct attempts, including its warmup, honestly record
`deadline_overrun`: the cooperative end-to-end target was 30 seconds and decoding
and result handling finished after the solver time limit. Its warmup returned
233 in 38.746720769 observed seconds, with an inner measured duration of
32.001985762 seconds. The three measured direct attempts slightly exceeded
30 seconds as listed. No failed/limited observation was replaced. The other
12 attempts, including their warmups, completed.

Partition sweeps reproduced the designed coordination barrier: department
choices at y=0 were already locally best, and flipping the platform alone lost
60 points. Exact children do not turn this coupled neighborhood search into an
original global certificate. Complete separator coverage solved both platform
branches; independent source feasibility and the source oracle separately
established value 259 for this model.

The notebook displays all 12 measured rows with their own phase/counter metadata;
it does not pair a median duration with another observation. Timings begin with
fresh construction and automatic compilation, include copy/solve, decode/source
audit and result construction, and use an outer complete-attempt wall timer to
capture dispatch/JIT work outside inner phase timers. Phase totals need not equal
that outer duration. The bounded child process took 250.695766 seconds including
startup/imports/artifact handling; its attempt loop took 135.717809155 seconds.
The Julia script's elapsed time was 250.331098788 seconds. Setup and imports are
therefore not hidden in a solver-only timing claim.

The separator variants' measured attempts were very short and variable. This
cohort supports their observed source quality, proof coverage and six-variable
capacity, not a general timing ranking between them or general solver superiority.
The structured oracle and the GLPK-on-QUBO formulation also limit generalization.
MIP search nodes are unavailable through this public sampler path and are never
replaced with the one returned incumbent sample. ExactSampler assignments come
from each actual sampler's public `optimizer.evaluations` result metadata.

## Frozen local allowance and observed work

The local allowance is 16 comparison attempts plus two separate fresh-kernel
correctness demonstrations, one each on Julia 1.10.11 and 1.12.6. The comparison
used all 16 attempts; the two kernel demonstrations remain unexecuted at this
audit checkpoint. Each notebook has one correctness solve and loads the saved
comparison rather than launching a campaign. Pure source/guard tests make no
compiler or solver optimize call and do not duplicate that solve.

| Method | Logical parent / max child | Reserved child calls / attempt | Reserved parent evaluations | Reserved Exact assignments |
| --- | --- | ---: | ---: | ---: |
| Direct GLPK MIPSampler | 49 / 49 | 1 | no decomposition scan | 0 |
| Complete separator, GLPK | 49 / 6 | 16 | 1029 | 0 |
| Partition sweeps, GLPK | 49 / 6 | 27 | 1729 | 0 |
| Complete separator, ExactSampler | 49 / 6 | 16 | 1029 | 1024 |

Separator bounds are two branches times eight components, each at most 64 rows.
Parent evaluations reserve `1 + 2*2 + 16*64 = 1029`. Partition permits at most
three sweeps of nine blocks and reserves `1+27*64=1729` candidates. Each attempt's
entire possible workload is reserved before compilation or search; failures
remain conservatively charged. There are no hidden compiler refinements.

The observed cohort used 16 compiler-only calls, 16 parent search calls,
204 backend calls, 4276 parent candidate evaluations and 4096 exact assignments.
Reservations were 240 backend calls, 15148 evaluations and 4096 assignments.
Every exact separator used all 1024 assigned child evaluations and all 1029
parent evaluations while still completing its public certificate. MIP separator
attempts used 16 calls and 21 parent evaluations; partition attempts used 18 calls
and 19 evaluations. Direct returned-state/source audits are not decomposition
candidate scans.

The two reserved kernel demonstrations add at most 32 backend calls, 2058 parent
evaluations and 2048 exact assignments. Across the local 16+2 allowance: at most
18 compiler-only calls, 18 parent search calls, 272 backend calls, 17206 parent
evaluations and 6144 exact assignments. This is a **local** allowance. Required
remote CI separately replays one correctness notebook per runtime per pushed
head, each bounded by one parent / 16 children / 1029 evaluations / 1024 exact
assignments. Remote attempts and reruns are recorded separately and are not
campaign observations. There is no global 18-solve claim or workflow change.

## Reproducibility and resources

The producing source was `9377a45d4f4f0627bec9171acb3037cf8e6776ba`.
The retained plan binds all nine application/runner/data/Project/lock/gate inputs
by SHA256. Subsequent publication prose may change; executable cells and all nine
bound inputs remain identical. The complete raw cohort contains one plan, all
16 attempt records, one summary and one process log (19 files, 64561 bytes).
No assignment archive, parent enumeration or observation selection is involved.
Historical experiment reports remain unchanged.

Both genuine focused runtime locks use published QUBODrivers 0.6.6,
QUBODecomposition 0.1.4, QUBOTools 0.16.2, ToQUBO 0.7.1, JuMP 1.32.1,
MathOptInterface 1.54.0 and GLPK 1.2.1. Independent fresh-depot imports and the
subsequent IJulia-context preparations passed without Project/lock drift. Every
focused dependency uses registry tracking. The former aggregate-seed refresh
retained old driver 0.6.5; isolated Project-only resolution generated these actual
locks. No generic helper or unrelated notebook was changed. GLPK is notebook-only;
preprocessing #16 is a separate gate and has no execution path here.

Commands used hard/soft 8 GiB RLIMIT_AS and one Julia/precompile/BLAS thread.
This is a virtual-address bound, not a cgroup RSS/no-swap claim. The campaign's
outer watchdog sent INT after at most 590 seconds with five seconds to KILL;
the owned-child launcher also enforced its 595-second deadline and 256 KiB log
cap. None fired in this run. Per-attempt 30-second deadlines are cooperative and
the direct overruns above are retained. Each text artifact is capped at 256 KiB
and the cohort at 4 MiB; actual retained files were below both limits. No native
annealer, hardware, paid backend or external-service optimization ran.

IJulia/Jupyter preparation and future local kernels use owned data/config/runtime
and IPython directories, an owned locked Python 3.12 docs environment, and
`IJULIA_NODEFAULTKERNEL=1`; HOME is never overridden. Earlier setup incident and
unknown user-kernel baseline are preserved in developer evidence. Subsequent
protected preparations and the campaign left the current user-kernel snapshots
unchanged. Notebook kernels need their own lifecycle/quiescence checks; campaign
watchdog evidence alone is not a kernel-cleanup claim.

## Developer acceptance audit

The comparison and pure guards passed; genuine fresh-kernel notebook outputs,
output hygiene/budgets, deterministic SVG, workshop export, strict book build,
final independent review, current-head CI and the substantive maintainer hold
remain acceptance checks. Reuse unchanged setup/guard evidence and avoid implicit
duplicate notebook solves. Preserve the two remaining local correctness calls.

PR180's historical workflow counters persist: posted review 1/3 used, formal
verification 3/3 reported spent, CI-fix trailer commits 3/3 used. The ordinary
implementation/setup/guard checks and fixed cohort do not reset those counters.
The maintainer hold still needs a substantive decision; no human approval or
final tutorial acceptance is inferred from dependency readiness or CI policy.
