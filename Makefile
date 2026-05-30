test:
	@if git grep -nE '(github\.com|raw\.githubusercontent\.com)/(psrenergy|psrnergy)/QUBO\.jl' -- '*.md' '*.ipynb' '*.yml' '*.yaml'; then \
		echo "Found legacy QUBO.jl repository links"; \
		exit 1; \
	fi

sysimage:
	julia -e 'using InteractiveUtils; versioninfo()'
	julia --project=./notebooks -e 'import Pkg; Pkg.instantiate()'
	julia --project=./scripts -e 'import Pkg; Pkg.instantiate()'
	julia --project=./scripts --threads=auto ./scripts/create_sysimage.jl
