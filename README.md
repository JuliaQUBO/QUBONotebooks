# QUBO-notebooks

<div align="center">
  <a href="https://github.com/JuliaQUBO/QUBO.jl">
    <img width="400px" src="https://raw.githubusercontent.com/JuliaQUBO/QUBO.jl/main/docs/src/assets/logo.svg" alt="QUBO.jl" />
  </a>
  <br>
  <span>Quantum Integer Programming Notebooks using <a href="https://jump.dev">JuMP</a> and <a href="https://github.com/JuliaQUBO/QUBO.jl">QUBO.jl</a>.</span>
  <br>
  <br>
  <a href="https://bernalde.github.io">David E. Bernal Neira</a>
  <br>
  <i>Davidson School of Chemical Engineering, Purdue University</i>
  <br>
  <i>Universities Space Research Association</i>
  <br>
  <i>NASA QuAIL</i>
  <br>
  <br>
  <a href="https://pedromxavier.github.io">Pedro Maciel Xavier</a>
  <br>
  <i>Davidson School of Chemical Engineering, Purdue University</i>
  <br>
  <i>Computer Science &amp; Systems Engineering Program, Federal University of Rio de Janeiro</i>
  <br>
  <i>PSR Energy Consulting &amp; Analytics</i>
  <br>
  <br>
</div>

## Notebooks

This repository keeps Julia and Python variants of the QuIP/QuIPML notebook
sequence. The stable local verification subset covers notebooks that do not
need credentials, proprietary/cloud solver access, local solver binaries, or
long benchmark runs.

Julia notebook number 6 is intentionally reserved for parity with the
Python-only QCi notebook. The Julia Five Starter Problems series therefore
starts at notebook 7.

| Topic | Julia notebook | Python notebook | Local verification status |
| --- | --- | --- | --- |
| Linear and Integer Programming | [notebooks_jl/1-MathProg.ipynb](notebooks_jl/1-MathProg.ipynb) | [notebooks_py/1-MathProg_python.ipynb](notebooks_py/1-MathProg_python.ipynb) | Julia notebook includes native Colab setup through the shared notebook project; local execution requires LP/NLP/MINLP solver binaries. |
| QUBO and Ising | [notebooks_jl/2-QUBO.ipynb](notebooks_jl/2-QUBO.ipynb) | [notebooks_py/2-QUBO_python.ipynb](notebooks_py/2-QUBO_python.ipynb) | Julia notebook includes native Colab setup through the shared notebook project; Python notebook is portable and covered by `make verify-qubo-python`. |
| Graver Augmented Multiseed Algorithm | [notebooks_jl/3-GAMA.ipynb](notebooks_jl/3-GAMA.ipynb) | [notebooks_py/3-GAMA_python.ipynb](notebooks_py/3-GAMA_python.ipynb) | Julia notebook includes native Colab setup through the shared notebook project; Python notebook is portable and covered by `make verify-gama-python`. |
| D-Wave | [notebooks_jl/4-DWave.ipynb](notebooks_jl/4-DWave.ipynb) | [notebooks_py/4-DWAVE_python.ipynb](notebooks_py/4-DWAVE_python.ipynb) | Julia notebook includes native Colab setup through the shared notebook project; quantum annealer cells require D-Wave solver access. The Python D-Wave notebook requires a user-managed Ocean install and is not part of the locked Python verification environment. |
| Benchmarking | [notebooks_jl/5-Benchmarking.ipynb](notebooks_jl/5-Benchmarking.ipynb) | [notebooks_py/5-Benchmarking_python.ipynb](notebooks_py/5-Benchmarking_python.ipynb) | Julia notebook includes native Colab setup through the shared notebook project; benchmark runs are long-running and generate artifacts. |
| QCi | Not available | [notebooks_py/6-QCi_python.ipynb](notebooks_py/6-QCi_python.ipynb) | Requires QCi API credentials and the QCi Python stack. |
| Canonical QUBO starter problems | [notebooks_jl/7-CanonicalProblems.ipynb](notebooks_jl/7-CanonicalProblems.ipynb) | Not available | Credential-free Julia notebook covered by `make verify-canonical-problems-julia`; exhaustive checks validate number partitioning, Max-Cut, and minimum vertex cover. |
| Order partitioning for A/B testing | [notebooks_jl/8-OrderPartitioning.ipynb](notebooks_jl/8-OrderPartitioning.ipynb) | Not available | Credential-free Julia notebook covered by `make verify-order-partitioning-julia`; all 64 assignments validate the grouped value/risk objective and decoded balances. |
| Altered cancer pathways from TCGA AML aggregates | [notebooks_jl/9-CancerGenomics.ipynb](notebooks_jl/9-CancerGenomics.ipynb) | Not available | Offline, credential-free Julia notebook covered by `make verify-cancer-genomics-julia`; a tiny incidence fixture is solved exhaustively and a seeded local sampler validates the committed aggregate without claiming clinical significance. |
| Local-first QAOA | [notebooks_jl/10-QAOA.ipynb](notebooks_jl/10-QAOA.ipynb) | Not available | Credential-free local Aer path covered by `make verify-qaoa-julia-local`; fixed seeds, exact baselines, circuit-resource audits, and a separate environment-gated IBM hardware cell keep the default tutorial bounded and service-free. |
| Local and quantum annealing | [notebooks_jl/11-Annealing.ipynb](notebooks_jl/11-Annealing.ipynb) | Not available | Seeded `DWave.Neal.Optimizer` runs for all five starter models are covered by `make verify-annealing-julia-local`; exact checks cover the small models, while the D-Wave QPU path is credentialed, fail-closed, and explicitly optional. |

### Five Starter Problems execution matrix

The local estimates below assume the Julia environment has already been
instantiated. A first run that downloads and precompiles packages can take
substantially longer. Remote-service runtimes include an unpredictable provider
queue after the local notebook work.

| Notebook or operation | Execution class | Make target | Expected runtime | Environment variables |
| --- | --- | --- | --- | --- |
| Canonical problems (7) | offline/portable | `make verify-canonical-problems-julia` | About 30–90 seconds | None required |
| Order partitioning (8) | offline/portable | `make verify-order-partitioning-julia` | About 30–90 seconds | None required |
| Cancer genomics (9) | offline/portable; opt-in live data refresh | `make verify-cancer-genomics-julia` | About 30–90 seconds | None required; reads only committed aggregates |
| QAOA (10) | local but heavyweight; opt-in IBM hardware | `make verify-qaoa-julia-local` | About 1–3 minutes | None required for local Aer |
| Annealing (11) | local but heavyweight; opt-in D-Wave QPU | `make verify-annealing-julia-local` | About 1–2 minutes | None required for local Neal |
| Complete stable local series | offline and local credential-free aggregate | `make verify-five-starter-problems-julia-local` | About 2–5 minutes | None required |
| Refresh committed TCGA AML aggregates | opt-in live data refresh | `make refresh-tcga-aml` | About 1–3 minutes, network-dependent | None required; public cBioPortal access |
| Submit the QAOA circuit | opt-in IBM hardware | `make verify-qaoa-julia-ibm` | Local QAOA time plus the IBM queue | `QUBONOTEBOOKS_QAOA_ENABLE_IBM=1`, `QUBONOTEBOOKS_QAOA_IBM_BACKEND`, and `QISKIT_IBM_TOKEN`; optional `QISKIT_IBM_CHANNEL` and `QISKIT_IBM_INSTANCE` |
| Submit the annealing example | opt-in D-Wave QPU | `make verify-annealing-julia-qpu` | Local Neal time plus the D-Wave queue | `QUBONOTEBOOKS_ANNEALING_ENABLE_QPU=1` and `DWAVE_API_TOKEN` |

The two hardware targets validate their opt-in variables before starting and
are excluded from default CI. Pass credentials only through the process
environment or an approved secret store. The local QAOA, local annealing, and
aggregate targets force their hardware switches off even if those switches are
set in the caller's environment; the aggregate target also never refreshes
data. All five notebook badges target `JuliaQUBO/QUBONotebooks` on the current
default branch, `main`.

### Attribution and clean-room reimplementation

This series is based on Mazumder and Tayur's
[*Five Starter Problems: Quantum Computing for Operations
Research*](https://doi.org/10.1287/educ.2025.0288), also available as an
[arXiv preprint](https://arxiv.org/abs/2401.08989). The
[companion repository](https://github.com/arulrhikm/Solving-QUBOs-on-Quantum-Computers)
is cited for context. The Julia notebooks are a clean-room reimplementation:
their code, prose, fixtures, and validation were written independently, with
the mathematical formulations checked against the published tutorial and cited
primary sources.

## Local verification

Python dependency groups are managed with [`uv`](https://docs.astral.sh/uv/).
The portable notebook execution target currently covers the Python QUBO and
GAMA notebooks and writes executed copies to `.nbverify/`:

```bash
make verify-python-portable
```

For narrower checks, run the unit/link tests or one portable notebook target:

```bash
make test
make test-python
make test-julia
make verify-qubo-python
make verify-gama-python
make verify-canonical-problems-julia
make verify-order-partitioning-julia
make verify-cancer-genomics-julia
make verify-qaoa-julia-local
make verify-annealing-julia-local
make verify-five-starter-problems-julia-local
```

The generic verifier can execute selected notebooks by overriding `NOTEBOOKS`
and `UV_GROUP_FLAGS`. The locked Python verification environment intentionally
excludes the D-Wave Ocean stack because its current cloud client depends on
`diskcache`, which has GitHub advisory GHSA-w8v5-vhqr-4h9v and no patched
release. Separate targets exist for notebooks that do not require external
solver credentials or longer-running jobs; those credentialed and long-running
notebooks are not part of the default portable subset. The QCi notebook does
not yet have a locked local make target because `eqc-models==0.19.0` requires
`networkx<3`, which conflicts with the D-Wave Ocean stack.
The Julia notebooks use `scripts/notebook_bootstrap.jl` in Colab to clone the
repository when needed, activate `notebooks_jl`, and resolve the checked-in
manifest for the current hosted Julia runtime. The bootstrap warms only the
imports used by the selected notebook.

```bash
make verify-notebooks NOTEBOOKS="notebooks_py/2-QUBO_python.ipynb" UV_GROUP_FLAGS="--group docs --group qubo"
make verify-benchmarking-python
```
