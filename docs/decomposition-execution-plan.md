# HiGHS decomposition comparison

The fixed synthetic application has 49 binary decisions: eight departments each
choose one of six alternatives, and a shared platform changes their value.
The child capacity is six logical variables. This comparison uses one warmup
and three measured repetitions for each of four methods, with all 16 attempts
retained in [summary.toml](../notebooks_data/decomposition_comparison/summary.toml).
No attempt failed, overran its deadline, or was retried/replaced.

## What the comparison shows

Both direct HiGHS and complete separator conditioning reach the source optimum
259. Partition sweeps stop at 205: improving this assignment requires changing
the platform and department choices together. Optimal block solves do not turn
that neighborhood search into a global algorithm.

| Method | Source value / gap | Public status | Three measured complete attempt times (seconds) |
| --- | --- | --- | --- |
| Direct HiGHS MIPSampler | 259 / 0 | `OPTIMAL` | 1.175007310, 1.133416197, 1.133503113 |
| Complete separator + HiGHS | 259 / 0 | `OPTIMAL` | 0.332408407, 0.375202660, 0.382582959 |
| Partition sweeps + HiGHS | 205 / 54 | `LOCALLY_SOLVED` | 0.288408093, 0.306895875, 0.346949649 |
| Complete separator + ExactSampler | 259 / 0 | `OPTIMAL` | 0.026520774, 0.028155162, 0.027918415 |

The gap here is `259 - source value`, using an independent source oracle, not
an inferred solver bound. Every returned assignment passed binary-domain,
one-choice-per-department, source-objective and compiled-energy checks. Complete
separator runs covered both platform branches. Direct HiGHS returned `OPTIMAL`;
the solver certificate remains subject to floating-point feasibility tolerances.
Partition results carry no global certificate.

These observations show that the example works with a stronger direct baseline.
The separator methods used smaller children and finished faster in these runs.
They do not establish general speedups: this is one deliberately structured
synthetic instance, its source oracle needs only 96 option evaluations, and
measurements ran on a shared development machine while other local validation
was active. No separately strengthened source MILP was measured. Do not compare
these times causally with the archived GLPK experiment: those were separate runs.

## Formulation and backend settings

All methods solve the same automatically compiled QUBO. Public compiler-only
`ToQUBO.Optimizer()` creates it without searching; public reformulation metadata
and `project_original_state` recover the source decisions. There are no manual
penalty hints or iterative penalty refinements. All compiled targets had 49
variables, no compiler auxiliaries and automatic one-choice penalties of -1492.
The full polynomial, including scaling and constants, was independently checked
against the source objective and penalties before dispatch.

`MIPSampler` exactly linearizes binary products before calling HiGHS. HiGHS does
not directly solve mixed-integer quadratic objectives. The direct linearization
has 160 product auxiliaries plus 49 logical binaries; a six-bit child has at most
15 product auxiliaries plus six logical binaries. These backend sizes are distinct
from decomposition's logical child capacity.

Direct and child MILPs use HiGHS.jl 1.24.0/native HiGHS 1.15.0, one thread,
`mip_rel_gap=0.0` and `mip_abs_gap=0.0`. There is no explicit HiGHS warm start.
Composite input starts are zero; ExactSampler enumerates all child assignments.
HiGHS and ExactSampler therefore do not share a consumed warm-start claim.

## Timing, work and bounds

Methods receive symmetric warmups, followed by rotating method order. Times
include fresh source construction, automatic compilation, copy/solve, decoding,
source validation and result construction. An outer timer also captures dispatch
and JIT work outside the phase timers. Each published time belongs to its own
repetition; no selected timing is paired with another observation's result.

The campaign process took 41.307421 seconds including startup, imports and
artifact handling; its attempt loop took 36.749222353 seconds. Warmup complete
attempts took 23.781439314, 4.564489775, 1.446975271 and 1.004176920 seconds for
direct, separator HiGHS, partition HiGHS and separator ExactSampler, respectively.
Warmups remain in the raw cohort and are excluded from the measured table.

Before dispatch, each attempt reserves its maximum possible workload. The
16-attempt campaign reserved 240 backend calls, 15148 parent evaluations and
4096 ExactSampler assignments. It actually used 204 backend calls, 4276 parent
evaluations and all 4096 exact assignments, plus 16 compiler-only invocations
and 16 top-level search invocations. MIP search nodes are unavailable through
this sampler path and are not represented by its single returned incumbent.

Each attempt has a cooperative 30-second deadline. The subprocess launcher has
a 595-second deadline plus at most four seconds of termination grace, an 8 GiB
virtual-address limit, one Julia/precompile/BLAS thread, a 256 KiB process-log
cap and a 4 MiB cohort cap. These are address-space bounds, not RSS/no-swap
claims. There are no paid or hardware backends. CI correctness replays are
separate from this retained comparison and never add campaign observations.

## Reproduction and provenance

The producing commit is `bc7b62e133886e997c756a85b866b550bfa10913`.
The retained plan binds nine executable/data/project/lock/release-gate inputs by
SHA256 and records the backend version/settings. The report loader rejects
stale hashes or an incomplete cohort. Both focused locks use registered
QUBODrivers 0.6.6, QUBODecomposition 0.1.4, QUBOTools 0.16.2, ToQUBO 0.7.1,
JuMP 1.32.1 and MathOptInterface 1.54.0, generated with Julia 1.10.11/1.12.6.

After installing the focused dependencies, reproduce into a new output directory:

```bash
python scripts/run_decomposition_campaign.py \
  --julia /absolute/path/to/julia-1.10.11 \
  --depot /absolute/path/to/owned/depot \
  --output /absolute/path/to/new-campaign
```

Commit executable changes before running: the runner requires a clean source
tree, freezes its plan before the first solve and never overwrites an existing
output directory. Retain failures rather than replacing them with successful
observations. For an ordinary correctness check, use
`make verify-decomposition-julia-local`; opening the notebook does not launch
this campaign. Its one exact separator demonstration is bounded by 16 children,
1029 parent evaluations and 1024 exact assignments.

The [historical GLPK summary](../notebooks_data/decomposition_comparison/history/glpk/README.md)
is byte-identical to the previously published cohort and retains its original
source/hash identities. It is not relabeled as HiGHS evidence.
