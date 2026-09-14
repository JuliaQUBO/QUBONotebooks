# Issue 138 measurement prototype

This branch is evidence for the CUDA-Q feasibility spike. Do not merge it.
Production dependency groups, verification targets, and notebook content belong
in the implementation issues after the spike's go/no-go decision.

The baseline is commit `7f886c1feb79ceedff6166c97c18ba4a167bd9ea`.
The candidate adds `cuda-quantum-cu13>=0.16.0,<0.17` in a dependency group
requiring Python >=3.11; the project still supports Python >=3.10,<3.13.

With uv 0.11.24, Python 3.12.12 and Python 3.10.19 available, and GLPK installed:

```sh
python scripts/issue138/measure.py /tmp/issue138-fresh --verify-portable
```

Choose a new empty directory. The harness writes complete logs and JSON results
under its `evidence` subdirectory. It creates separate virtual environments and
a private cache, hides GPUs, and limits OpenMP and OpenBLAS to two threads.
Python installation and apt installation are prerequisites, outside sync timing.

Measurements distinguish:

- Cold installation of **docs + qubo + cudaq**, with no cached wheel artifacts.
- No-op synchronization of an already installed environment.
- Recreating a deleted environment from its retained local cache. This does not
  measure downloading or restoring a GitHub Actions cache archive.
- Full environment size and the incremental size over **docs + qubo**, measured
  with `du -sb` (apparent bytes, including each directory's metadata).
- Free filesystem space before and after installation, which captures hardlink
  sharing between uv's cache and the environments.
- Independent seeded CPU processes, using both a GHZ circuit and a circuit with
  varied measurement probabilities plus an analytically known expectation.
- CUDA-free portable execution at both baseline and candidate. Sequential timings
  are diagnostic samples; identical dependency exports are the stronger evidence
  that the optional group does not add work to the existing target.

The scratch-only Actions workflow runs the harness on two independent
`ubuntu-22.04` jobs and uploads its evidence for 30 days. Keep the issue comment's
numerical summary and commit references as the durable record.

No hosted Colab runtime is connected to this prototype. A local or Actions run
must not be represented as a hosted Colab measurement.
