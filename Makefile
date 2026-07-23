.PHONY: test sysimage test-python test-julia check-notebook-output-hygiene clear-notebook-outputs refresh-tcga-aml verify-notebooks verify-python-portable verify-qubo-python verify-gama-python verify-benchmarking-python verify-canonical-problems-julia verify-order-partitioning-julia verify-cancer-genomics-julia

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
CANONICAL_PROBLEMS_JULIA_NOTEBOOK ?= notebooks_jl/7-CanonicalProblems.ipynb
ORDER_PARTITIONING_JULIA_NOTEBOOK ?= notebooks_jl/8-OrderPartitioning.ipynb
CANCER_GENOMICS_JULIA_NOTEBOOK ?= notebooks_jl/9-CancerGenomics.ipynb
NOTEBOOKS ?= $(PORTABLE_PYTHON_NOTEBOOKS)
NOTEBOOK_FILES ?= notebooks_jl/*.ipynb notebooks_py/*.ipynb

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

check-notebook-output-hygiene:
	@if git grep -lE 'C:\\\\Users|AppData|purdue-internship|QUBONotebooksFork|home/azain' -- $(NOTEBOOK_FILES); then \
		echo "Found stale or personal notebook output paths"; \
		exit 1; \
	fi

clear-notebook-outputs:
	$(PYTHON) -m jupyter nbconvert --ClearOutputPreprocessor.enabled=True --inplace $(NOTEBOOK_FILES)

refresh-tcga-aml:
	$(PYTHON) ./scripts/fetch_tcga_aml.py

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

verify-canonical-problems-julia:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="--group docs" NOTEBOOKS="$(CANONICAL_PROBLEMS_JULIA_NOTEBOOK)"

verify-order-partitioning-julia:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="--group docs" NOTEBOOKS="$(ORDER_PARTITIONING_JULIA_NOTEBOOK)"

verify-cancer-genomics-julia:
	$(MAKE) verify-notebooks UV_GROUP_FLAGS="--group docs" NOTEBOOKS="$(CANCER_GENOMICS_JULIA_NOTEBOOK)"
