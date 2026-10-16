# Department/platform tutorial: proposed bounded execution plan

Status: **not executed; root review/authorization required**. This plan does not
reset PR180's historical workflow budgets: 1/3 posted reviews used, 3/3 formal
verification passes reported spent, 3/3 CI-fix trailer commits used. Ordinary
implementation tests are distinct from another formal verification pass.

## Source and release prerequisites

Continue PR180 at `9b7795a161d81c093953bc6018aaa01673245557`, base
`9111f2be8fac92c3e11a5e73484ad9a3c3e52b5c`. Commit reviewed application/test/docs
sources first. No campaign begins on a dirty tree. Output publication is a later
output-only commit with identical cell sources. Bind Julia source, fixed data,
runner, Project, both actual manifests and release gate by SHA256 before solving.

`RELEASE-GATES.toml` is ready for published QUBODrivers 0.6.6 and registered
QUBODecomposition 0.1.4, including standalone #17/#18. Both runtime locks were
generated from isolated Project-only registry resolution, then independently
instantiated/imported in fresh depots without Project/lock drift. Versions,
registered trees and actual imported source paths were checked; no optimizer or
compiler optimize call ran. This is dependency adoption, not application or
notebook validation. GLPK is a notebook-only dependency. No source/path override
or manufactured lock/version is supplied. Future refreshes must preserve this
normal registry provenance; the unchanged generic aggregate-seed helper retained
old driver 0.6.5 and failed this minimum-version transition.

## Fixed model and independent reference

Eight departments, six alternatives, one platform: 49 source binaries. The
fixed displayed synthetic TOML table uses annual net-value points and platform
cost 60. The source problem maximizes
`sum((b[g,i]+c[g,i]*y)*x[g,i])-60y`, with exactly one alternative per department
and every x/y binary. The independent reference computes the two platform
branch optima 205 and 259 using 96 scalar option evaluations per oracle call;
it does not enumerate the parent. Freeze coefficients before any outcome and
do not tune them after inspecting results.

Use public compiler-only `ToQUBO.Optimizer()`, ordinary default automatic
penalties, `optimize!(source_model)`, `TargetModel()`,
`reformulation_metadata` and `project_original_state`. No penalty hints,
private state injection or refinement overrides. Public applied penalties and
complete source ownership are inspected. Compiler dispatches zero search
solvers. Each attempt then performs exactly one manually budgeted extracted-QUBO
solve; there is no iterative penalty refinement or automatic retry. Do not claim
JuMP source primals/status from the compiler-only call. Infeasible decoding is a
retained failure. Any future attached-solver/refinement path needs a new shared
nested-call plan, not the same allowance relabeled.

Before any backend factory, require actual compiled dimension 49, no auxiliary
bits, one identity target bit per source binary, complete mapping coverage and
exactly eight six-variable connected residual components after removing the
platform. Refuse unexpected encoding growth or cross-department interactions.
The entire compiled constant/linear/quadratic polynomial is independently
compared with the source coefficients plus the automatically applied one-choice
penalties before dispatch (including binary diagonals and MOI scaling).
There are at most 168 nonzero off-diagonal edges, so the inspected direct
MIPSampler product linearization adds at most 168 backend binaries to the 49
logical ones (217 total). That backend size is different from child logical size.

## Local allowance: 16 comparison attempts and two correctness demonstrations

The proposal is **18 local top-level search solves**. No local allowance has yet been
used. The source guard tests execute no search solver and do not rerun the large
notebook call. Do not add convenience solves in another cell or test.

- Exactly 16 campaign attempts on one fixed documented runtime: four methods,
  one symmetric warmup and three measured repetitions each. Primary runtime is
  Julia 1.10.11. No pooling Julia 1.12 timings into that cohort.
- Exactly two separate fresh-kernel correctness demonstrations: one real
  ExactSampler complete separator invocation per documented runtime (1.10.11
  and 1.12.6). Each notebook has only one large search call.
- No retries, replacement observations, tuning, extra grids, native annealer,
  hardware, paid backend or hidden compiler refinement. Retain failures, limits,
  started-but-killed attempts and unused schedule entries explicitly.

| Method | Logical parent / child limit | Calls reserved per attempt | Parent candidate evaluations reserved | Exact assignments reserved |
| --- | --- | ---: | ---: | ---: |
| Direct GLPK MIPSampler | 49 / 49 | 1 | no decomposition scan; audit returned full state | 0 |
| Complete separator, GLPK MIPSampler | 49 / 6 | 16 | 1029 | 0 |
| Partition sweeps, GLPK MIPSampler | 49 / 6 | 27 | 1729 | 0 |
| Complete separator, actual ExactSampler | 49 / 6 | 16 | 1029 | 1024 |

Separator bounds are two branches times eight components, each at most 64 rows.
Parent evaluations are `1 + 2*2 + 16*64 = 1029` (initial incumbent, two full
branch evaluations per branch, all child rows). Partition allows three sweeps
of nine blocks (eight departments plus platform singleton), at most 27 child
calls; conservative candidate bound is `1+27*64=1729`. Stagnation can stop early.
MIP returns one sample but its search nodes remain an unknown/different work
unit; the same conservative parent allowance does not imply equal work.

Reserve each attempt's entire possible exact workload before compilation or
search. Charge failures conservatively; never reconstruct unknown work as zero.
The campaign ledger enforces at most 16 attempts, 240 backend search calls,
15148 decomposition candidate evaluations and 4096 ExactSampler assignments.
The two correctness calls add at most 32 backend calls, 2058 parent evaluations
and 2048 exact assignments. Across all 18 local solves: at most 18 compiler-only optimize
calls, 18 manually requested parent/search optimize calls, 272 backend search
calls, 17206 decomposition evaluations and 6144 exact assignments. The direct
rows' separate returned-state/source audits are not called decomposition scans.
No source oracle is a backend optimizer call.

Required remote CI separately executes one fresh-kernel correctness replay on
Julia 1.10 and one on Julia 1.12 for each pushed head. Each invocation has the
same one parent / at most 16 child calls, 1029 parent evaluations and 1024 exact
assignments. A complete two-runtime CI pair therefore reserves at most 32 child
calls, 2058 parent evaluations and 2048 assignments. These are remote correctness
replays, not measured campaign observations or part of the 18-local-solve budget.
Record actual remote attempts, failures and reruns per head separately; do not
claim a global 18-solve limit. The revised local source has not been pushed and
has no remote correctness result yet. No CI workflow changes are proposed.

Use fresh instances and the same GLPK factory/settings for the first three
methods, with no explicit solver warm start. Composite input defaults to zero;
GLPK initializes internally. Do not claim identical consumed starts. Warm up all
four methods once, then rotate method order over the three measured rounds as
frozen by the runner. Keep every observation; do not select a different run to
obtain a preferred quality/timing combination.

## Resources, costs and retained artifacts

Every Julia command, including setup/probes, must receive root's hard 8 GiB
RLIMIT_AS, a timeout <=600 seconds, one Julia/precompile/BLAS thread and an owned
writable depot over read-only caches. This is a virtual-address bound, not a
cgroup RSS/no-swap claim. One heavy command at a time. Use approved local sockets
only for notebook kernels. Setup authorization covered lock generation and imports
only; solver, compiler optimize, kernel and campaign execution remain ungranted.

Each attempt has 30 seconds of available end-to-end time; pass the remainder
(after construction/compilation/copy preparation) to the solver/parent. This is
cooperative: compilation, exact certificate work and opaque children can overrun.
A whole-command 600-second OS timeout bounds the campaign; if it fires, retain
incomplete attempts and stop without replacement. Record unsupported deadline
forwarding and actual overruns rather than treating the cap as proof of completion.

Measure fresh source/data/model construction, automatic compilation, copy/solve,
decode/source audit, result construction and complete per-attempt wall time.
Record import/environment/JIT setup and whole-process elapsed separately; artifact
writing is included in process elapsed, outside per-attempt solve measurements.
Failures also retain observed elapsed time and all cumulative reservations.
Actual ExactSampler evaluations come from each unchanged sampler's public result
metadata, not inferred from one returned row. MIP search nodes are unavailable
through this public path and must be labeled unknown, not set to one.

The proposed opt-in `scripts/run_decomposition_campaign.py` launcher applies
the address/thread controls, stops at 595 seconds with bounded termination grace,
and caps its process log at 256 KiB; exceeding the cap terminates the attempt
group without replacement. Its ownership, EOF/missing/closed-stdout, timeout
and log-limit paths have been checked only with tiny inert Python subprocesses;
no Julia campaign or solver has executed. Root must inspect/approve the exact
command and runtime behavior before use.

Write a new output directory only. Save immutable plan/source hashes first, then
an atomic started record for each scheduled attempt before dispatch, its actual
status/failure and cumulative ledger afterwards, and a final summary only when
all 16 attempts return. Preserve raw output and exceptions. Maximum retained raw
artifacts: 16 attempt TOMLs, one plan TOML, one summary TOML, one process log,
source/environment hash inventory; bound each text artifact to 256 KiB and the
cohort to 4 MiB (reject oversized artifacts, without losing the already saved
started record). No full 49-bit enumeration/sample archive is written.

The final notebook must display genuine retained measured observations bound to
its actual source/environment, all measured repetitions including failures,
source objectives/feasibility/gaps, compiled values, statuses/proof coverage,
parent/max child sizes, calls/assignments/evaluations and phase/complete costs.
No fabricated pending-state result is acceptable at final publication. Keep
historical reports unchanged. Do not infer a speedup from smaller children; if
measurements are short/noisy or mixed, state that and emphasize capacity/quality.

## Implementation validation and acceptance gates

Static preparation covered notebook JSON/source inspection, light Python syntax,
96-option arithmetic and policy/structure checks. Subsequent bounded setup ran
Pkg resolution and fresh-depot package imports only. Application Julia guards,
notebooks, solvers, kernels, builds and this campaign remain unexecuted. Before
later execution:

1. Preserve the completed real release adoption and both genuine locks; repeat
   affected setup checks if those inputs change.
2. Root approves this exact 16+2 allocation, resource wrapper and artifact limits.
3. Commit the reviewed source; perform ordinary changed-behavior tests, numerical
   guards, `make test`, relevant Python/Julia tests and clean install/cache probes.
4. Run the 16-attempt campaign once, retain every artifact, inspect/report its
   actual outcomes, then run one fresh-kernel correctness demonstration per runtime.
5. Commit genuine notebook outputs without altering executed sources. Check output
   hygiene/budgets, deterministic diagram reproduction, workshop export, strict
   book build and workflow lint if affected. Preserve the 18-notebook aggregate
   budget arithmetic and every other notebook's outputs.
6. Use a remaining independent review round for the substantive rewrite. Do not
   silently launch a fourth formal verification or CI-repair cycle. Root resolves
   the maintainer hold and obtains any precise final decision required by that
   record; zero required formal approvals do not establish human acceptance.
