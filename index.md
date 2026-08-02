# QUBONotebooks: Quantum Integer Programming

This book collects Julia and Python notebooks for learning mathematical
programming, quadratic unconstrained binary optimization, and quantum and
quantum-inspired optimization workflows. The notebooks pair mathematical
formulations with executable examples, local validation, and explicitly gated
cloud-hardware paths.

Notebook outputs are generated before publication rather than during the site
build. This keeps the public book reproducible without placing solver
credentials in GitHub Actions or consuming cloud-service credits on every
documentation build.

## Notebook map

| Topic | Python | Julia |
| --- | --- | --- |
| Mathematical Programming | [1-MathProg_python.ipynb](notebooks_py/1-MathProg_python.ipynb) | [1-MathProg.ipynb](notebooks_jl/1-MathProg.ipynb) |
| QUBO and Ising Models | [2-QUBO_python.ipynb](notebooks_py/2-QUBO_python.ipynb) | [2-QUBO.ipynb](notebooks_jl/2-QUBO.ipynb) |
| Graver Augmentation Multiseed Algorithm | [3-GAMA_python.ipynb](notebooks_py/3-GAMA_python.ipynb) | [3-GAMA.ipynb](notebooks_jl/3-GAMA.ipynb) |
| D-Wave | [4-DWAVE_python.ipynb](notebooks_py/4-DWAVE_python.ipynb) | [4-DWave.ipynb](notebooks_jl/4-DWave.ipynb) |
| Benchmarking | [5-Benchmarking_python.ipynb](notebooks_py/5-Benchmarking_python.ipynb) | [5-Benchmarking.ipynb](notebooks_jl/5-Benchmarking.ipynb) |
| QCI | [6-QCi_python.ipynb](notebooks_py/6-QCi_python.ipynb) | [6-QCi.ipynb](notebooks_jl/6-QCi.ipynb) |
| Canonical QUBO problems | — | [7-CanonicalProblems.ipynb](notebooks_jl/7-CanonicalProblems.ipynb) |
| Order partitioning for A/B testing | — | [8-OrderPartitioning.ipynb](notebooks_jl/8-OrderPartitioning.ipynb) |
| Altered cancer pathways | — | [9-CancerGenomics.ipynb](notebooks_jl/9-CancerGenomics.ipynb) |
| Local-first QAOA | — | [10-QAOA.ipynb](notebooks_jl/10-QAOA.ipynb) |
| Local and quantum annealing | — | [11-Annealing.ipynb](notebooks_jl/11-Annealing.ipynb) |

See [Local Setup](local-setup.md) to build the book or reproduce notebook
outputs. Each notebook page also provides an **Open in Colab** action.
