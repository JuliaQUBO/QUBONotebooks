# Contributing

This file records the editorial contracts for the notebook collection: what
each notebook family promises, what binds every notebook regardless of
language, and how much committed output a notebook may carry.

Operational documentation lives elsewhere. The [README](README.md) covers
dependency groups, verification targets, and the Julia and Colab environments;
[local-setup.md](local-setup.md) covers building the book and re-executing
notebooks locally.

## Notebook families

The repository publishes eleven Julia notebooks and six Python notebooks.
Notebooks 1 through 6 exist in both languages; notebooks 7 through 11 are Julia
only.

### The Python notebooks are on-ramps, not mirrors

The Python notebooks are introductory on-ramps. Most people arriving at
quantum optimization arrive from Python, and Pyomo, `dimod`, `neal`, and
`eqc_models` are Python-native APIs that read most naturally there. The paired
presentation is deliberate pedagogy: the same model in both languages, then a
push toward the Julia tooling that the rest of the collection builds on.

They are maintained for correctness and for the shared contracts listed below.

They are **not** maintained for structural parity with their Julia
counterparts. A Python notebook may use different section names, a different
number of sections, a different example, or a different ordering than the
Julia notebook it is paired with, and that is not a defect.

The reason is drift. An implied mirror turns a single convention change into a
seventeen-file edit, and the mirror then slips in ways that look like
sloppiness: one family's section renamed while the other kept the old title,
one family abbreviating a term the other spells out. Requiring parity without
enforcing it produces exactly that class of defect and no way to catch it.
Notebooks 7 through 11 already have no Python counterpart, so the asymmetry is
the existing precedent rather than a new concession.

A change that *does* alter a shared contract must be applied to both families.
A change that only reorganizes one notebook's prose or examples need not be
mirrored.

### Contracts that bind every notebook

These hold for all seventeen notebooks in both families and are enforced by
`tests/test_notebook_structure.py`, which runs under `make test-python`. Run
it before opening a pull request. `make test` is a separate target covering
the repository link policy, not these contracts.

| Contract | What it requires |
| --- | --- |
| Masthead | The first cell is markdown and opens with the exact shared block: one H1 matching the notebook's `myst.yml` table-of-contents title, its anchor `<div>`, the JuliaQUBO attribution, the SECQUOIA and PSR Energy links, and a Colab badge. The badge URL is pinned to this repository on `main` and to the notebook's own path, so a badge repointed at a fork or a feature branch fails. |
| Single H1 | Exactly one level-one heading per notebook, and no raw `<h1>`. |
| Heading hierarchy | No heading level is skipped outside fenced code blocks, so the rendered page has a navigable section tree. |
| Unindented raw HTML | Every line of a raw-HTML markdown block starts at column zero. A four-space indent publishes the tags as literal source in engines without CommonMark HTML blocks. |
| Hidden installation cells | Installation, bootstrap, and `versioninfo()` code cells, and any install-titled section outside `## Setup`, carry both the `hide-cell` and `installation` tags. |
| Exercise checkpoints | At least three cells marked `# EXERCISE` and three marked with the exact string `# SOLUTION (hidden in workshop version):` — the short `# SOLUTION` form is not counted. The first three solution cells carry the `hide-cell` and `solution` tags; every solution cell must contain real code, not only comments. |
| Footer structure | Acknowledgments sections and back-to-top links are selected structurally, by heading and in-page anchor, rather than by prose phrase. |
| In-page anchors | Anchor identifiers are unique across the whole project, and every `#`-link resolves inside its own notebook. |
| Relative links | Every relative link in a notebook, `index.md`, `local-setup.md`, `README.md`, or this file resolves to a file that exists. |
| Colab routes | Every notebook in the table of contents has both a slash and a dot route in `colab.html`, with no duplicate keys. |

One further contract binds the Python family alone: Python notebooks carry
portable `python3` kernel metadata, so they open without a machine-specific
kernel name.

### Table of contents

The book's table of contents presents each Julia and Python pair as equals,
and that is deliberate. Both notebooks in a pair are published, correct, and
maintained; labelling the Python entry as secondary in the navigation would
misrepresent the paired pedagogy and read as "unmaintained", which is the
opposite of the contract above. The asymmetry that a reader needs is already
structural: notebooks 7 through 11 appear under their own Julia section, and
the notebook map in [index.md](index.md) marks their missing Python
counterparts.

## Committed notebook outputs

Notebook outputs are generated before publication and committed. The book
build never executes a notebook, so committed outputs are what the published
site renders, and they keep the book reproducible without putting solver
credentials into GitHub Actions or spending cloud credits on every docs build.

Clearing outputs is therefore not an acceptable way to shrink a notebook.

### Size budgets

Stored output is the dominant term in this repository's artifact size, and a
re-execution can add a large image or a duplicated payload without any visible
change to the lesson. These budgets bound that drift:

| Scope | Budget |
| --- | --- |
| One code cell | 256 KB of stored output |
| One notebook | 1.0 MB of stored output |
| All notebooks | 10 MB of stored output |

Measure stored output as the serialized `outputs` array of every code cell,
not the notebook's file size.

### Documented exceptions

These exceed a budget by deliberate grant rather than by accident:

| Notebook or cell | Budget exceeded | What the stored output is |
| --- | --- | --- |
| `notebooks_py/5-Benchmarking_python.ipynb` | notebook, and one cell | A `nx.draw` spring-layout rendering of the random Ising model graph |
| `notebooks_jl/5-Benchmarking.ipynb` | notebook, and one cell | A circular-layout plot of the same Ising graph |
| `notebooks_py/4-DWAVE_python.ipynb` | two cells | The QPU topology graph and the minor-embedding graph |
| `notebooks_py/1-MathProg_python.ipynb` | notebook | Nine stored plots holding 1.14 MB of the notebook's 1.16 MB. Eight are near-identical redraws of the same feasible region, each adding one annotation for the LP, ILP, convex INLP, and nonconvex INLP solutions; the ninth is an unrelated complexity-growth plot |

Two different failures are visible in that table, and they need different
remedies. Every cell over the per-cell budget is a dense graph-layout render,
where the lever is rasterization and resolution rather than fewer results.
`1-MathProg_python` is the opposite case: no single cell is close to the
per-cell budget, and the notebook is over only because one figure is stored
eight times over. That duplication is exactly what the per-notebook budget
exists to catch.

An exception is a decision to revisit, not a permanent allowance. Reducing a
grant, by rendering a figure at a lower resolution or in a more compact format
or by not re-emitting an unchanged figure, is an improvement as long as the
instruction survives it.

### Changing outputs

When a change re-executes a notebook, check the resulting stored-output size
against the budgets above. Growth past a budget needs either a reduction or a
new documented exception in the table, decided in review rather than merged
silently. Adding a figure to a notebook that already holds an exception is the
case most likely to pass unnoticed.

Committed outputs must not carry credentials, tokens, or machine-specific
absolute paths; `make check-notebook-output-hygiene` guards the known personal
path patterns.
