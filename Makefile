sysimage:
	julia -e 'using InteractiveUtils; versioninfo()'
	julia --project=./notebooks_jl -e 'import Pkg; Pkg.instantiate()'
	julia --project=./scripts -e 'import Pkg; Pkg.instantiate()'
	julia --project=./scripts --threads=auto ./scripts/create_sysimage.jl
