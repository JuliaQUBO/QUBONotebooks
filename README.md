# QUBONotebooks

<div align="center">
  <a href="https://github.com/JuliaQUBO/QUBO.jl">
    <img width="400px" src="https://raw.githubusercontent.com/JuliaQUBO/QUBO.jl/main/docs/src/assets/logo.svg" alt="QUBO.jl" />
  </a>
  <br>
  <span>Quantum Integer Programming Notebooks using <a href="https://jump.dev">JuMP</a> and <a href="https://github.com/JuliaQUBO/QUBO.jl">QUBO.jl</a>.</span>
  <br>
  <br>
  <b>Maintained by the <a href="https://github.com/JuliaQUBO">JuliaQUBO</a> organization</b>
  <br>
  <br>
  <a href="https://secquoia.github.io/">SECQUOIA</a>
  &nbsp;&middot;&nbsp;
  <a href="https://www.psr-inc.com/">PSR Energy</a>
  <br>
  <br>
</div>

This collection is maintained by the
[JuliaQUBO](https://github.com/JuliaQUBO) organization, in collaboration with
[SECQUOIA](https://secquoia.github.io/) and
[PSR Energy](https://www.psr-inc.com/). Individual notebook contributors are
credited in the Acknowledgments section at the end of each notebook.

[CONTRIBUTING.md](CONTRIBUTING.md) records the editorial contracts: what each
notebook family promises, the structural contracts that bind every notebook,
and the committed-output size budgets.

## Read the notebooks online

The notebooks are published as a Jupyter Book at
**<https://juliaqubo.github.io/QUBONotebooks/>**, with navigation across the
Julia and Python series and an "Open in Colab" action on every notebook page.

## Jupyter Book

The source landing page is [index.md](index.md), and
[local-setup.md](local-setup.md) documents the local book build and
notebook-output workflow.

Build the book from the repository root with:

```bash
uv sync --locked --group docs
make build-book
```

The site build uses committed notebook outputs and does not execute notebooks
or contact external solvers. Every pull request and every push to `main` runs
the same command through `.github/workflows/jupyter-book.yml`; pushes to `main`
also deploy the built site to GitHub Pages.

The build runs in `--strict` mode, so it is a real gate, but it deliberately
does not gate on other people's uptime:

| Problem | Build result |
| --- | --- |
| Unresolved cross-reference | fails |
| Unreachable external URL | warns |
| DOI metadata lookup failure | warns |

Broken *relative* links are covered separately by
`test_relative_links_point_at_files_that_exist`, which resolves them against
the filesystem without network access. External link rot therefore shows up as
a build warning rather than an intermittently red default branch.

## Notebooks

This repository keeps Julia and Python variants of the QuIP/QuIPML notebook
sequence. The stable local verification subset covers notebooks that do not
need credentials, proprietary/cloud solver access, local solver binaries, or
long benchmark runs.

The Python notebooks are introductory on-ramps, maintained for correctness and
for the shared structural contracts, but not for section-by-section parity
with their Julia counterparts. See
[Notebook families](CONTRIBUTING.md#notebook-families).

Notebook 6 has Julia and Python variants. The Julia notebook uses the
supported QCIOpt.jl QUBO workflow and explicitly maps the continuous or
constrained Python examples that do not have direct Julia equivalents. The
Julia Five Starter Problems series starts at notebook 7 and reimplements the
tutorial cited under [Source of the Five Starter
Problems](#source-of-the-five-starter-problems).

| Topic | Julia notebook | Python notebook | Local verification status |
| --- | --- | --- | --- |
| Linear and Integer Programming | [notebooks_jl/1-MathProg.ipynb](notebooks_jl/1-MathProg.ipynb) | [notebooks_py/1-MathProg_python.ipynb](notebooks_py/1-MathProg_python.ipynb) | Julia notebook includes native Colab setup through its focused notebook project; local execution requires LP/NLP/MINLP solver binaries. |
| QUBO and Ising | [notebooks_jl/2-QUBO.ipynb](notebooks_jl/2-QUBO.ipynb) | [notebooks_py/2-QUBO_python.ipynb](notebooks_py/2-QUBO_python.ipynb) | Julia notebook includes native Colab setup through its focused notebook project; Python notebook is portable and covered by `make verify-qubo-python`. |
| Graver Augmented Multiseed Algorithm | [notebooks_jl/3-GAMA.ipynb](notebooks_jl/3-GAMA.ipynb) | [notebooks_py/3-GAMA_python.ipynb](notebooks_py/3-GAMA_python.ipynb) | Julia notebook includes native Colab setup through its focused notebook project; Python notebook is portable and covered by `make verify-gama-python`. |
| D-Wave | [notebooks_jl/4-DWave.ipynb](notebooks_jl/4-DWave.ipynb) | [notebooks_py/4-DWAVE_python.ipynb](notebooks_py/4-DWAVE_python.ipynb) | Julia notebook includes native Colab setup through its focused notebook project; quantum annealer cells require D-Wave solver access. The Python D-Wave notebook requires a user-managed Ocean install and is not part of the locked Python verification environment. |
| Benchmarking | [notebooks_jl/5-Benchmarking.ipynb](notebooks_jl/5-Benchmarking.ipynb) | [notebooks_py/5-Benchmarking_python.ipynb](notebooks_py/5-Benchmarking_python.ipynb) | Julia notebook includes native Colab setup through its focused notebook project; benchmark runs are long-running and generate artifacts. |
| QCi | [notebooks_jl/6-QCi.ipynb](notebooks_jl/6-QCi.ipynb) | [notebooks_py/6-QCi_python.ipynb](notebooks_py/6-QCi_python.ipynb) | The Julia notebook uses QCIOpt's default CondaPkg environment; its model-construction and exact-enumeration path is credential-free and covered by `make verify-qci-julia-local`. QCI submission is a separate explicit opt-in. The Python notebook requires its separate `eqc-models` stack and credentials for cloud examples. |
| Canonical QUBO starter problems | [notebooks_jl/7-CanonicalProblems.ipynb](notebooks_jl/7-CanonicalProblems.ipynb) | Not available | Credential-free Julia notebook covered by `make verify-canonical-problems-julia`; exhaustive checks validate number partitioning, Max-Cut, and minimum vertex cover. |
| Order partitioning for A/B testing | [notebooks_jl/8-OrderPartitioning.ipynb](notebooks_jl/8-OrderPartitioning.ipynb) | Not available | Credential-free Julia notebook covered by `make verify-order-partitioning-julia`; all 64 assignments validate the grouped value/risk objective and decoded balances. |
| Altered cancer pathways from TCGA AML aggregates | [notebooks_jl/9-CancerGenomics.ipynb](notebooks_jl/9-CancerGenomics.ipynb) | Not available | Offline, credential-free Julia notebook covered by `make verify-cancer-genomics-julia`; a tiny incidence fixture is solved exhaustively and a seeded local sampler validates the committed aggregate without claiming clinical significance. |
| Local-first QAOA | [notebooks_jl/10-QAOA.ipynb](notebooks_jl/10-QAOA.ipynb) | Not available | Credential-free local Aer path covered by `make verify-qaoa-julia-local`; fixed seeds, exact baselines, circuit-resource audits, and a separate environment-gated IBM hardware cell keep the default tutorial bounded and service-free. |
| Local simulated and quantum annealing | [notebooks_jl/11-Annealing.ipynb](notebooks_jl/11-Annealing.ipynb) | Not available | Seeded `DWave.Neal.Optimizer` runs for all five starter models are covered by `make verify-annealing-julia-local`; exact checks cover the small models, while the D-Wave QPU path is credentialed, fail-closed, and explicitly optional. |

### Julia QCi and Five Starter Problems execution matrix

The local estimates below assume the Julia environment has already been
instantiated. A first run that downloads and precompiles packages can take
substantially longer. Remote-service runtimes include an unpredictable provider
queue after the local notebook work.

| Notebook or operation | Execution class | Make target | Expected runtime | Environment variables |
| --- | --- | --- | --- | --- |
| QCi Julia local path (6) | offline/model-only; opt-in QCI cloud | `make verify-qci-julia-local` | About 30–90 seconds after the environment is ready | None required |
| Canonical problems (7) | offline/portable | `make verify-canonical-problems-julia` | About 30–90 seconds | None required |
| Order partitioning (8) | offline/portable | `make verify-order-partitioning-julia` | About 30–90 seconds | None required |
| Cancer genomics (9) | offline/portable; opt-in live data refresh | `make verify-cancer-genomics-julia` | About 30–90 seconds | None required; reads only committed aggregates |
| QAOA (10) | local but heavyweight; opt-in IBM hardware | `make verify-qaoa-julia-local` | About 1–3 minutes | None required for local Aer |
| Annealing (11) | local but heavyweight; opt-in D-Wave QPU | `make verify-annealing-julia-local` | About 1–2 minutes | None required for local Neal |
| Complete stable local series | offline and local credential-free aggregate | `make verify-five-starter-problems-julia-local` | About 2–5 minutes | None required |
| Refresh committed TCGA AML aggregates | opt-in live data refresh | `make refresh-tcga-aml` | About 1–3 minutes, network-dependent | None required; public cBioPortal access |
| Submit the QCi QUBO | opt-in QCI cloud | `make verify-qci-julia-cloud` | Local validation time plus the QCI queue | `QUBONOTEBOOKS_QCI_ENABLE_CLOUD=1` and `QCI_TOKEN` |
| Submit the QAOA circuit | opt-in IBM hardware | `make verify-qaoa-julia-ibm` | Local QAOA time plus the IBM queue | `QUBONOTEBOOKS_QAOA_ENABLE_IBM=1`, `QUBONOTEBOOKS_QAOA_IBM_BACKEND`, and `QISKIT_IBM_TOKEN`; optional `QISKIT_IBM_CHANNEL` and `QISKIT_IBM_INSTANCE` |
| Submit the annealing example | opt-in D-Wave QPU | `make verify-annealing-julia-qpu` | Local Neal time plus the D-Wave queue | `QUBONOTEBOOKS_ANNEALING_ENABLE_QPU=1` and `DWAVE_API_TOKEN` |

The three live-service targets validate their opt-in variables before starting,
fail unless a provider job is submitted, and are excluded from default CI.
Pass credentials only through the process environment or an approved secret
store. The local QCi, local QAOA, local annealing, and aggregate targets force
their provider switches and submission requirements off even if those values
are set in the caller's environment; the aggregate target also never refreshes
data. All six Julia notebook badges in this matrix target
`JuliaQUBO/QUBONotebooks` on the current default branch, `main`.

## Source of the Five Starter Problems

Notebooks 7 through 11 reimplement the five starter problems introduced in:

> A. R. Mazumder and S. Tayur, *Five Starter Problems: Solving Quadratic
> Unconstrained Binary Optimization Models on Quantum Computers*, in
> **TutORials in Operations Research**, INFORMS (2025), pp. 145–183.
> DOI: [10.1287/educ.2025.0288](https://doi.org/10.1287/educ.2025.0288)

The tutorial is also available as an
[arXiv preprint](https://arxiv.org/abs/2401.08989), and the authors publish a
[companion repository](https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers)
that is cited here for context.

### Clean-room reimplementation

The Julia notebooks are a clean-room reimplementation: their code, prose,
fixtures, and validation were written independently, with the mathematical
formulations checked against the published tutorial and cited primary sources.
No source cells, prose, saved output, or assets were copied from the companion
repository. Each of notebooks 7 through 11 repeats this citation in its own
References section.

## Local verification

Python dependency groups are managed with [`uv`](https://docs.astral.sh/uv/).
The portable notebook execution target covers the Python QUBO and
GAMA notebooks and writes executed copies to `.nbverify/`:

```bash
make verify-python-portable
```

For narrower checks, run the unit/link tests or one portable notebook target:

```bash
make test
make test-python
make test-julia
make test-qciopt-dwave-coexistence
make verify-qubo-python
make verify-gama-python
make verify-qci-julia-local
make verify-canonical-problems-julia
make verify-order-partitioning-julia
make verify-cancer-genomics-julia
make verify-qaoa-julia-local
make verify-annealing-julia-local
make verify-five-starter-problems-julia-local
make verify-colab-bootstrap-output JULIA="julia +1.12"
make verify-colab-hosted
```

### Test design

Add a test when it protects a contract that can fail silently:

- derive and compare both sides of a relationship that must stay synchronized;
- execute behavior and assert its result; or
- guard a deliberate policy whose removal would otherwise leave every check
  green.

Avoid pinning documentation wording, literal notebook source lines, or build
target declarations. Invoking a build target is the behavioral check for
whether it exists. When a literal is unavoidable, use the narrowest stable
symbol or configuration key and leave a comment naming the recurring defect
class it protects.

### Python verification environment

The generic verifier can execute selected notebooks by overriding `NOTEBOOKS`
and `UV_GROUP_FLAGS`. The locked Python verification environment intentionally
excludes the D-Wave Ocean stack because its current cloud client depends on
`diskcache`, which has GitHub advisory GHSA-w8v5-vhqr-4h9v and no patched
release. Separate targets exist for notebooks that do not require external
solver credentials or longer-running jobs; those credentialed and long-running
notebooks are not part of the default portable subset. The Python QCi notebook
does not have a locked local make target because `eqc-models==0.19.0` requires
`networkx<3`, which conflicts with the D-Wave Ocean stack.

### Julia notebook environments

The Julia notebooks
avoid that cross-notebook coupling by activating one focused environment from
`notebooks_jl/environments/<notebook-key>`. The root `notebooks_jl` project is
the aggregate IJulia/sysimage and compatibility-test environment; it is not the
project shown to a notebook learner. Its QCIOpt/DWave coexistence contract is
still guarded by `make test-qciopt-dwave-coexistence`. After changing an
aggregate dependency, maintainers refresh both focused lock sets with
`make refresh-julia-notebook-environments JULIA="julia +1.10"` and then
`make refresh-julia-notebook-environments JULIA="julia +1.12"`.

### Colab Python bridge

In native
Colab, every Python-backed Julia
notebook binds PythonCall to the hosted Python runtime before Julia package
instantiation. The bootstrap records both PythonCall's executable and
CondaPkg's `Null` backend as Julia preferences, because these packages decide
whether to compile CondaPkg and its micromamba or pixi backends before runtime
environment variables alone can take effect. Those preferences are written to
the selected notebook project. Notebooks 2–5, 9, and 11 ensure
the Ocean stack, notebook 6 ensures only `numpy` and `requests`, and notebook 10
requests QiskitOpt's versioned Qiskit, Aer, IBM Runtime, Optimization, and SciPy
stack (plus their transitive dependencies). This keeps one notebook's Python
bridge and compatibility constraints out of every other notebook's setup.
On a cold Julia 1.12 IJulia kernel, QCIOpt, QiskitOpt, and the
IJulia/PythonCall extension can otherwise emit failed-task-printer notices
during their first implicit compilation even when the imports succeed.

### Deferred package imports

Every notebook keeps package loading out of the default bootstrap and routes
each real import cell through the shared Colab-aware output-suppressed loader.
Notebooks 1–5 retain their lesson-scoped deferred import boundaries, while
notebooks 6–11 load one declared package group. Real package-load failures
still propagate from the helper.

### Colab bootstrap

The Julia notebooks use `scripts/notebook_bootstrap.jl` in Colab to clone the
repository when needed, activate
`notebooks_jl/environments/<notebook-key>`, and select that project's checked-in
manifest for the hosted Julia minor version. Every focused project has locks
for Julia 1.10.11 and Julia 1.12.6. Automatic selected-project
precompilation and broad eager import warm-up are disabled during setup so a
fresh runtime does not front-load compilation for packages the learner may not
use.
Set `QUBONOTEBOOKS_WARM_PACKAGES=1` to warm a notebook's declared imports or
`QUBONOTEBOOKS_PRECOMPILE=1` to explicitly precompile the selected project.

### Colab bootstrap smoke check

`make verify-colab-bootstrap-output JULIA="julia +1.12"` executes the real
setup, activation, and every marked real import cell from all Julia notebooks
through fresh IJulia kernels with Colab environment markers. It rejects
CondaPkg or package/artifact transcripts, manifest mismatch warnings, and pip
progress in the bootstrap output. No synthetic aggregate import is substituted;
activation and import cells must remain free of
CondaPkg environment setup, failed-task output, stack traces, cell errors, and
unexpected rendered values.
The smoke provides `pip`, Matplotlib, NumPy, and requests only in its isolated
runtime so notebooks can exercise Colab's preinstalled Python baseline without
adding the Ocean stack to the locked project environment.

For a cold test on Google's current hosted image, install the official Colab
CLI and run the hosted target after pushing the commit under test:

```bash
uv tool install --force git+https://github.com/googlecolab/google-colab-cli
make verify-colab-hosted
```

The first invocation that contacts Colab prompts for Google OAuth. By default,
the target tests all 11 Julia notebooks in separate fresh hosted CPU VMs so one
notebook's compiled package cache cannot hide another notebook's cold-start
behavior. Each invocation fetches the exact current Git commit, executes the
real bootstrap, activation, and marked import cells through Colab's native
`julia` kernelspec, rejects CondaPkg setup and failed-task output, rejects
bootstrap cells slower than three minutes, and releases its VM when the command
finishes. Select a narrower set of committed notebook keys with, for example,

```bash
QUBONOTEBOOKS_COLAB_NOTEBOOKS="9-CancerGenomics,11-Annealing" \
  make verify-colab-hosted
```

The hosted target consumes Colab quota and is intentionally an explicit
maintainer acceptance test rather than part of ordinary GitHub Actions. A
multi-notebook selection still uses one auto-released VM per notebook and can
therefore take substantially longer than a single-notebook check.

```bash
make verify-notebooks NOTEBOOKS="notebooks_py/2-QUBO_python.ipynb" UV_GROUP_FLAGS="--group docs --group qubo"
make verify-benchmarking-python
```
