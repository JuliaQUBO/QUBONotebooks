# Local setup

This repository uses `uv` for the Python environment and focused Julia
projects under `notebooks_jl/environments/`.

## Build the book

From the repository root, install the locked documentation environment and
build the static site:

```bash
uv sync --locked --group docs
make build-book
```

Jupyter Book 2 also uses Node.js; confirm that `node` and `npm` are available
if the build reports a missing frontend tool. The generated site is written to
`_build/html/index.html`.

## Execute notebooks

Portable and credential-free execution targets write refreshed copies to
`.nbverify/`:

```bash
make verify-python-portable
make verify-qci-julia-local
make verify-five-starter-problems-julia-local
```

Additional targets and environment details are listed in the repository
[README](README.md). In particular, Julia notebooks activate their own focused
projects, and the Python QCI notebook uses a separate dependency environment
from the D-Wave notebooks because their NetworkX constraints conflict.

Cloud execution is always explicit. Provide credentials only through the
process environment or an approved secret store. QCI submission requires
`QUBONOTEBOOKS_QCI_ENABLE_CLOUD=1` and `QCI_TOKEN`; D-Wave QPU submission
requires the corresponding QPU opt-in and `DWAVE_API_TOKEN`. Do not rerun or
replace committed D-Wave QPU outputs unless new QPU access and credits have
been deliberately approved.

The book build itself never executes notebooks or contacts a cloud solver.
