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
make verify-qci-julia-local
make verify-five-starter-problems-julia-local
```

Additional targets and environment details are listed in the repository
[README](https://github.com/JuliaQUBO/QUBONotebooks/blob/main/README.md). In
particular, Julia notebooks activate their own focused projects, and the Python
QCI notebook uses a separate dependency environment from the D-Wave notebooks
because their NetworkX constraints conflict.

## Commercial solvers

The Julia mathematical-programming notebook has optional sections that use
commercial solvers. Neither solver is required for the core examples, and
neither is installed by the notebook project.

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
