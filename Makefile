sysimage:
	julia -e 'using InteractiveUtils; versioninfo()'
    julia --project=notebooks -e 'using Pkg; Pkg.instantiate()'
    julia --project=scripts --threads=auto ./scripts/create_sysimage.jl
