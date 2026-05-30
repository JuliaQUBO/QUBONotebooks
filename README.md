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

## Table of contents

1. [Linear and Integer Programming](notebooks/1-LP_IP.ipynb)
2. [Quadratic Unconstrained Binary Optimization](notebooks/2-QUBO.ipynb)
3. [Graver Augmented Multiseed Algorithm](notebooks/3-GAMA.ipynb)

## Local verification

Python dependency groups are managed with [`uv`](https://docs.astral.sh/uv/).
The portable notebook execution target currently covers the Python QUBO
notebook and writes executed copies to `.nbverify/`:

```bash
make verify-qubo-python
```

For a narrower check, run the Python unit tests and Julia link tests:

```bash
make test-python
make test-julia
```

The generic verifier can execute selected notebooks by overriding `NOTEBOOKS`
and `UV_GROUP_FLAGS`. Some notebooks still require external solver binaries
until the remaining QuIP notebook fixes are migrated.

```bash
make verify-notebooks NOTEBOOKS="notebooks_py/2-QUBO_python.ipynb" UV_GROUP_FLAGS="--group docs --group qubo"
```
