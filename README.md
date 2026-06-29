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

| Topic | Julia notebook | Python notebook | Local verification status |
| --- | --- | --- | --- |
| Linear and Integer Programming | [notebooks_jl/1-MathProg.ipynb](notebooks_jl/1-MathProg.ipynb) | [notebooks_py/1-MathProg_python.ipynb](notebooks_py/1-MathProg_python.ipynb) | Requires local LP/NLP/MINLP solver binaries. |
| QUBO and Ising | [notebooks_jl/2-QUBO.ipynb](notebooks_jl/2-QUBO.ipynb) | [notebooks_py/2-QUBO_python.ipynb](notebooks_py/2-QUBO_python.ipynb) | Python notebook is portable and covered by `make verify-qubo-python`. |
| Graver Augmented Multiseed Algorithm | [notebooks_jl/3-GAMA.ipynb](notebooks_jl/3-GAMA.ipynb) | [notebooks_py/3-GAMA_python.ipynb](notebooks_py/3-GAMA_python.ipynb) | Python notebook is portable and covered by `make verify-gama-python`. |
| D-Wave | [notebooks_jl/4-DWave.ipynb](notebooks_jl/4-DWave.ipynb) | [notebooks_py/4-DWAVE_python.ipynb](notebooks_py/4-DWAVE_python.ipynb) | Requires D-Wave solver access for quantum annealer cells. |
| Benchmarking | [notebooks_jl/5-Benchmarking.ipynb](notebooks_jl/5-Benchmarking.ipynb) | [notebooks_py/5-Benchmarking_python.ipynb](notebooks_py/5-Benchmarking_python.ipynb) | Long-running benchmark notebook with generated artifacts. |
| QCi | Not available | [notebooks_py/6-QCi_python.ipynb](notebooks_py/6-QCi_python.ipynb) | Requires QCi API credentials and the QCi Python stack. |

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
```

The generic verifier can execute selected notebooks by overriding `NOTEBOOKS`
and `UV_GROUP_FLAGS`. The portable QUBO/GAMA dependency group is intentionally
separate from the D-Wave Ocean stack, which is only installed by
`make verify-dwave-python`. Separate targets exist for notebooks that require
external solver credentials or longer-running jobs; those targets are not part
of the default portable subset. The QCi notebook does not yet have a locked
local make target because `eqc-models==0.19.0` requires `networkx<3`, which
conflicts with the D-Wave Ocean stack.

```bash
make verify-notebooks NOTEBOOKS="notebooks_py/2-QUBO_python.ipynb" UV_GROUP_FLAGS="--group docs --group qubo"
make verify-dwave-python
make verify-benchmarking-python
```
