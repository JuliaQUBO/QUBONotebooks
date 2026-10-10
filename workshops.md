# Teaching with QUBONotebooks

Build student and instructor editions from the maintained notebooks:

```bash
make workshops
```

The command creates `dist/workshops/student.zip` and
`dist/workshops/instructor.zip`, plus unpacked copies beside them. Give students
the student ZIP; retain the instructor ZIP for demonstrations and discussion.
Each edition includes the notebook data, benchmark summaries, Julia bootstrap,
and locked environments needed by the lessons. Package installation still
requires internet access on a fresh machine.

Student copies remove solution cells and clear outputs from exercise cells.
Instructor copies expose the solutions. Both keep the worked examples and
their figures, so learners can read the lessons before running them. The
published book continues to show the complete source collection.

An existing output directory is protected from replacement, including any
notes or answers added after export. Use a new destination for another session:

```bash
python3 scripts/export_workshops.py --output-dir dist/autumn-workshop
```

To export one edition, add `--edition student` or `--edition instructor`.
The `workshop-manifest.json` inside each edition records the source commit,
whether the checkout had local changes, and the packaged file hashes. The
**Workshop bundles** GitHub Actions workflow also provides downloadable ZIPs
as run artifacts on pull requests, pushes to `main`, and manual runs.

## Before the session

Unzip an edition and open a terminal in its `student` or `instructor` directory.
For the introductory Python route, install the locked environment and start
JupyterLab from that directory:

```bash
uv sync --locked --group docs --group qubo
uv run --locked --group docs --group qubo jupyter lab
```

For Julia, follow [Local Setup](local-setup.md) to prepare a Julia kernel, then
run each notebook's setup cells to activate its focused project. Keep the
exported directory tree together: the notebooks use relative paths to their
data and bootstrap scripts.

For Colab, upload the exported `.ipynb` file using **File → Upload notebook**.
The generated copies replace the original Colab badges with this instruction
so learners open the chosen workshop edition. Julia's setup can download its
runtime support from the repository when needed.

Before teaching, run the chosen route on the machines or hosted runtimes the
class will use. Complete downloads and compilation ahead of the session. The
plans below estimate teaching time and assume basic familiarity with binary
variables and probability; they exclude installation and lunch. Use the local
solver paths throughout. CUDA-Q and hardware submissions are optional additions
for sessions with the corresponding environments already prepared.

## A 60-minute introduction

Use [QUBO and Ising in Python](notebooks_py/2-QUBO_python.ipynb).

| Minutes | Activity |
| --- | --- |
| 0–10 | Introduce binary decisions and write a small quadratic objective. |
| 10–30 | Work through the QUBO/Ising conversion and compare energies. |
| 30–45 | Discuss constraints and the penalty parameter in the worked example. |
| 45–60 | Attempt the practice checkpoints, then compare with the instructor solutions. |

## A half-day Python workshop

| Minutes | Activity |
| --- | --- |
| 0–20 | Establish the problem, notation, and local notebook workflow. |
| 20–65 | Model and solve examples in [QUBO and Ising](notebooks_py/2-QUBO_python.ipynb). |
| 65–110 | Explore augmentation and its checkpoints in [GAMA](notebooks_py/3-GAMA_python.ipynb). |
| 110–120 | Break. |
| 120–165 | Run the local simulated-annealing examples in [D-Wave](notebooks_py/4-DWAVE_python.ipynb). |
| 165–180 | Compare feasibility, solution quality, randomness, and computational budgets. |

## A full-day modeling and methods workshop

Follow the half-day route above, then continue with prepared Julia environments:

| Minutes | Activity |
| --- | --- |
| 180–225 | Derive and exactly check selected [canonical problems](notebooks_jl/7-CanonicalProblems.ipynb). |
| 225–265 | Interpret the tradeoffs in [order partitioning](notebooks_jl/8-OrderPartitioning.ipynb). |
| 265–280 | Break. |
| 280–330 | Compare a shared small model using [local QAOA](notebooks_jl/10-QAOA.ipynb) and [annealing](notebooks_jl/11-Annealing.ipynb). |
| 330–360 | Design a fair experiment using the metrics and prepared plots in [Benchmarking](notebooks_py/5-Benchmarking_python.ipynb). |

Select examples within the longer lessons rather than trying to execute every
cell during class. Use the committed benchmark summaries for discussion; full
benchmark regeneration belongs in follow-up work. Ask learners to distinguish
the original objective, penalized energy, feasibility, and observed success
frequency when they explain a result.

## A 60-minute Julia decomposition session

After preparing the [focused development environment](README.md#decomposition-development-environment),
use [Decomposition and Reconstruction](notebooks_jl/12-Decomposition.ipynb).
The exported bundles include both Julia runtime locks and the immutable source
pin; installation needs internet, and the subsequent solves need no credentials.

| Minutes | Activity |
| --- | --- |
| 0–15 | Compare direct solving with independent components; audit the full energy. |
| 15–30 | Enumerate a supplied separator and inspect reconstruction maps. |
| 30–40 | Explain why exact neighborhood solves can stagnate. |
| 40–50 | Decode the constrained model under weak and sufficient penalties. |
| 50–60 | Attempt the three exercises and discuss statuses versus oracle evidence. |

## Maintaining workshop editions

Edit the canonical notebooks and regenerate the bundles. Mark answer cells with
the `solution` tag; the exporter also recognizes existing `# SOLUTION` markers.
Keep exercise prompts under the existing `# EXERCISE` markers or an `exercise`
tag. Runtime assets must be tracked by Git to enter a bundle; local caches,
credentials, and untracked files are excluded.

The export tests exercise solution removal, instructor visibility, preservation
of worked outputs, reproducible archives, and protection of existing workshop
directories. Source notebooks remain the published and tested collection.
