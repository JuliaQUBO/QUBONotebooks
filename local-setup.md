# Local setup

This repository uses `uv` for the Python environment and focused Julia
projects under `notebooks_jl/environments/`.

## Install Julia

If you do not have a Julia installation yet, consider using
[juliaup](https://github.com/JuliaLang/juliaup), which installs Julia and keeps
several versions side by side. The Julia notebook projects carry locks for
Julia 1.10.11 and Julia 1.12.6.

Instantiate the notebook project once from the repository root:

```bash
julia --project=notebooks_jl -e 'using Pkg; Pkg.instantiate()'
```

Each Julia notebook activates that project when it runs locally. In Colab the
bootstrap selects the focused project under
`notebooks_jl/environments/<notebook-key>` instead, so no manual installation
step is needed there.

To report the version you are actually running, start Julia and call
`versioninfo()`. Instantiating against an incompatible release fails at the
notebook's setup cell, so this is a diagnostic rather than a required step.

## Build the book

From the repository root, install the locked documentation environment and
build the static site:

```bash
uv sync --locked --group docs
make build-book
```

Jupyter Book 2 also uses Node.js; confirm that `node` and `npm` are available
if the build reports a missing frontend tool. The generated site is written to
`_build/html/`. Serve it instead of opening `index.html` directly:

```bash
python -m http.server --directory _build/html
```

Open the URL printed by the server. `make build-book` targets a site root by
default; CI sets `BASE_URL=/QUBONotebooks` for the GitHub Pages project path.

## Execute notebooks

Portable and credential-free execution targets write refreshed copies to
`.nbverify/`:

```bash
make verify-python-portable
make verify-dwave-python-local
make verify-qci-julia-local
make verify-five-starter-problems-julia-local
```

Additional targets and environment details are listed in the repository
[README](https://github.com/JuliaQUBO/QUBONotebooks/blob/main/README.md). In
particular, Julia notebooks activate their own focused projects, and the Python
QCI notebook uses a separate dependency environment from the D-Wave notebooks
because their NetworkX constraints conflict.

## D-Wave Python local execution

`make verify-dwave-python-local` uses the existing locked `docs` and `qubo`
groups on Python 3.10–3.12. It checks seeded local samples against exhaustive
enumeration and executes the notebook without importing the Ocean cloud
client, reading saved QPU configuration, or contacting Leap. The target forces
`QUBONOTEBOOKS_DWAVE_ENABLE_QPU=0` even if the caller enabled it. CI runs this
path in a separate job with a 10-minute budget.

Hardware demonstrations require a separately managed Ocean environment and
`QUBONOTEBOOKS_DWAVE_ENABLE_QPU=1` before opening or executing the notebook.
Use `DWAVE_API_TOKEN`, Colab Secrets, or your existing Ocean local configuration.
Opted-in connectivity and submission errors stop execution. The Ocean cloud
client remains outside the lock because it brings in `diskcache`, which the
repository dependency policy excludes. Published QPU outputs are retained
historical examples; local verification writes its own results to `.nbverify/`.

## Optional CUDA-Q

CUDA-Q is an optional dependency group for CPU quantum simulation. On Python
3.11 or 3.12, install and verify it from the repository root with:

```bash
make verify-cudaq-python
```

The target installs `docs`, `qubo`, and `cudaq`, checks a Bell-state circuit
using `qpp-cpu`, and executes the D-Wave Python notebook with QPU access forced
off. The Bell check verifies both sampled bitstrings and exact expectations;
installation or simulation failures stop verification. The annealing and QAOA
teaching sections are follow-up work in issues
[#141](https://github.com/JuliaQUBO/QUBONotebooks/issues/141) and
[#140](https://github.com/JuliaQUBO/QUBONotebooks/issues/140). Add the QUBO
notebook to `CUDAQ_PYTHON_NOTEBOOKS` when its guarded section lands.

To install without running verification:

```bash
uv sync --locked --group docs --group qubo --group cudaq
```

The group pins the CUDA-Q distribution line `cuda-quantum-cu13>=0.16.0,<0.17`
and requires Python 3.11+. Python 3.10 remains supported by the portable groups;
requesting `cudaq` on 3.10 fails explicitly. The default and portable groups
exclude CUDA-Q. Running a portable target afterwards synchronizes back to its
smaller environment; use `UV_PROJECT_ENVIRONMENT=/path/to/separate/venv` to keep
an optional environment separately.

Published wheels cover Linux x86_64/aarch64 (glibc 2.28+) and macOS Apple
Silicon (macOS 13+). Native Windows and Intel macOS have no wheels for this
release. Linux x86_64 on Ubuntu 22.04 and WSL2 was tested; the other wheel
platforms were not executed. Hosted Colab installation remains unmeasured.
The CPU target needs no GPU or CUDA driver, but the distribution still downloads
GPU libraries.

The [#138 measurements](https://github.com/JuliaQUBO/QUBONotebooks/issues/138#issuecomment-5671304635)
on two fresh Ubuntu 22.04 runners found a **2.91 GB** complete environment,
**2.33 GB** more than `docs` + `qubo`, about **1.48 GB** of additional wheel
payload, and a **2.91 GB** uv cache (decimal GB). Cold synchronization took
**9.7–41.0 seconds**. Allow space for both the environment and cache; filesystem
sharing can affect actual disk use. These are measured release/platform
figures, not cross-platform guarantees.

A separate CPU workflow runs on changes to the optional dependency, target,
verifier, tests, and relevant notebooks, or by manual dispatch. It has a
10-minute limit and no persistent CUDA-Q cache. Existing CI jobs retain their
original targets and installed groups. No GPU execution target is provided.

## Commercial solvers

No notebook in this collection calls a commercial solver, and neither solver
below is a dependency of any notebook project. They are documented here because
the notebooks are a starting point for your own models, where an LP/MIP or
MINLP licence is often worth having. The mathematical-programming notebook,
the one where a commercial solver would otherwise be expected, solves its
examples with GLPK, Cbc, Ipopt, Bonmin, and Couenne, all open source.

**Gurobi** is one of the most powerful LP and MIP solvers available today, and
free academic licences are offered. Visit
[the Gurobi website](https://www.gurobi.com/), create an account, preferably
with an academic email address, and obtain a licence. You can then download and
use the software.

**BARON** is one of the most powerful MINLP solvers available today. Students
from the University System of Georgia and CMU and UIUC affiliates are eligible
for a free licence. Visit [the BARON website](https://www.minlp.com/home),
create an account with an academic email address, and obtain a licence. You can
then download and use the software.

## Credentials

Cloud execution is always explicit. Provide credentials only through the
process environment or an approved secret store. QCI submission requires
`QUBONOTEBOOKS_QCI_ENABLE_CLOUD=1` and `QCI_TOKEN`; D-Wave QPU submission
requires the corresponding QPU opt-in and `DWAVE_API_TOKEN`. Do not rerun or
replace committed D-Wave QPU outputs unless new QPU access and credits have
been deliberately approved.

The book build itself never executes notebooks or contacts a cloud solver.
