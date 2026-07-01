.PHONY: test sysimage test-python test-julia verify-notebooks verify-python-portable verify-qubo-python verify-gama-python verify-benchmarking-python

PYTHON ?= python3
UV ?= uv
UV_CACHE_DIR ?= $(CURDIR)/.uv-cache
UV_GROUP_FLAGS ?= --group docs --group qubo
PORTABLE_UV_GROUP_FLAGS ?= --group docs --group qubo
BENCHMARKING_UV_GROUP_FLAGS ?= --group docs --group qubo
JULIA ?= julia
JULIA_DEPOT_PATH ?= $(CURDIR)/.julia-depot:$(HOME)/.julia
JULIA_PKG_PRECOMPILE_AUTO ?= 0
QUBO_PYTHON_NOTEBOOK ?= notebooks_py/2-QUBO_python.ipynb
GAMA_PYTHON_NOTEBOOK ?= notebooks_py/3-GAMA_python.ipynb
PORTABLE_PYTHON_NOTEBOOKS ?= $(QUBO_PYTHON_NOTEBOOK) $(GAMA_PYTHON_NOTEBOOK)
DWAVE_PYTHON_NOTEBOOK ?= notebooks_py/4-DWAVE_python.ipynb
BENCHMARKING_PYTHON_NOTEBOOK ?= notebooks_py/5-Benchmarking_python.ipynb
NOTEBOOKS ?= $(PORTABLE_PYTHON_NOTEBOOKS)

test:
	@if git grep -nE '(github\.com|raw\.githubusercontent\.com)/(psrenergy|psrnergy)/QUBO\.jl' -- '*.md' '*.ipynb' '*.yml' '*.yaml'; then \
		echo "Found legacy QUBO.jl repository links"; \
		exit 1; \
	fi
	@if git grep -nE '(github|raw\.githubusercontent\.com)/(pedromxavier/QUBO-notebooks|AlbertLee125/QUBONotebooks|SECQUOIA/QUBONotebooks)' -- '*.md' '*.ipynb' '*.yml' '*.yaml'; then \
		echo "Found stale QUBONotebooks repository links"; \
		exit 1; \
	fi

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

verify-python-portable:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="$(PORTABLE_UV_GROUP_FLAGS)" NOTEBOOKS="$(PORTABLE_PYTHON_NOTEBOOKS)"

verify-qubo-python:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="$(PORTABLE_UV_GROUP_FLAGS)" NOTEBOOKS="$(QUBO_PYTHON_NOTEBOOK)"

verify-gama-python:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="$(PORTABLE_UV_GROUP_FLAGS)" NOTEBOOKS="$(GAMA_PYTHON_NOTEBOOK)"

verify-benchmarking-python:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="$(BENCHMARKING_UV_GROUP_FLAGS)" NOTEBOOKS="$(BENCHMARKING_PYTHON_NOTEBOOK)"
