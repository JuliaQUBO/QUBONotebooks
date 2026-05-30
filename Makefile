.PHONY: sysimage test-python test-julia verify-notebooks verify-qubo-python

PYTHON ?= python3
UV ?= uv
UV_CACHE_DIR ?= $(CURDIR)/.uv-cache
UV_GROUP_FLAGS ?= --group docs --group qubo
JULIA ?= julia
JULIA_DEPOT_PATH ?= $(CURDIR)/.julia-depot:$(HOME)/.julia
JULIA_PKG_PRECOMPILE_AUTO ?= 0
NOTEBOOKS ?= notebooks_py/2-QUBO_python.ipynb

sysimage:
	$(JULIA) -e 'using InteractiveUtils; versioninfo()'
	JULIA_DEPOT_PATH=$(JULIA_DEPOT_PATH) JULIA_PKG_PRECOMPILE_AUTO=$(JULIA_PKG_PRECOMPILE_AUTO) $(JULIA) --project=./notebooks_jl -e 'import Pkg; Pkg.instantiate()'
	JULIA_DEPOT_PATH=$(JULIA_DEPOT_PATH) JULIA_PKG_PRECOMPILE_AUTO=$(JULIA_PKG_PRECOMPILE_AUTO) $(JULIA) --project=./scripts -e 'import Pkg; Pkg.instantiate()'
	JULIA_DEPOT_PATH=$(JULIA_DEPOT_PATH) $(JULIA) --project=./scripts --threads=auto ./scripts/create_sysimage.jl

test-python:
	$(PYTHON) -m unittest discover -s tests

test-julia:
	$(JULIA) --startup-file=no test/runtests.jl

verify-notebooks:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(UV) sync --locked $(UV_GROUP_FLAGS)
	UV_CACHE_DIR=$(UV_CACHE_DIR) JULIA_DEPOT_PATH=$(JULIA_DEPOT_PATH) JULIA_PKG_PRECOMPILE_AUTO=$(JULIA_PKG_PRECOMPILE_AUTO) $(UV) run --locked $(UV_GROUP_FLAGS) python ./scripts/verify_notebooks.py $(NOTEBOOKS)

verify-qubo-python:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="--group docs --group qubo" NOTEBOOKS="notebooks_py/2-QUBO_python.ipynb"
