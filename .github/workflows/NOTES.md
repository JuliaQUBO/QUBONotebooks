# ${TITLE} Release Notes

## Downloading

```shell
wget "https://github.com/JuliaQUBO/QUBONotebooks/releases/${TAG}/download/sysimage.tar.gz" -O sysimage.tar.gz

mkdir -p /content/.julia-depot
tar -xzf sysimage.tar.gz -C /content # sysimage.so, Project.toml, Manifest.toml
export JULIA_DEPOT_PATH="/content/.julia-depot:${JULIA_DEPOT_PATH:-$HOME/.julia}"
julia --project=/content -e 'import Pkg; Pkg.instantiate()'
julia --project=/content --sysimage=/content/sysimage.so
```

### SHA256

```text
${SHA_256}
```
