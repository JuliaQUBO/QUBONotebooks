module QUBONotebooksBootstrap

using Dates
using Logging
import Pkg
import TOML

const WORKSPACE = normpath(joinpath(@__DIR__, ".."))
const NOTEBOOKS_DIRNAME = "notebooks_jl"
const ALLOW_VERSION_MISMATCH_ENV = "QUBONOTEBOOKS_ALLOW_JULIA_VERSION_MISMATCH"
const REPO_REF_ENV = "QUBONOTEBOOKS_REPO_REF"
const PRECOMPILE_ENV = "QUBONOTEBOOKS_PRECOMPILE"
const PYTHON_STACK_NOTEBOOKS = Set((
    "2-QUBO",
    "3-GAMA",
    "4-DWave",
    "5-Benchmarking",
))
const CREDENTIAL_FREE_DWAVE_NOTEBOOKS = Set((
    "9-CancerGenomics",
    "11-Annealing",
))
const NOTEBOOK_IMPORTS = Dict(
    "1-MathProg" => :(using Plots, JuMP, GLPK, Cbc, Ipopt, SpecialFunctions, AmplNLWriter, Bonmin_jll, Couenne_jll),
    "2-QUBO" => :(using Karnak, LinearAlgebra, Graphs, JuMP, QUBO, Plots, GLPK, DWave, Luxor),
    "3-GAMA" => :(using BinaryWrappers, DelimitedFiles, Downloads, NPZ, JuMP, DWave, LinearAlgebra, Measures, Random, Plots, StatsBase, StatsPlots, lib4ti2_jll),
    "4-DWave" => :(using LinearAlgebra, Plots, JuMP, QUBO, DWave, Graphs),
    "5-Benchmarking" => :(using JuMP, QUBO, LinearAlgebra, Plots, Measures, DWave, Random, Statistics, ZipFile, JSON, StatsBase),
    "7-CanonicalProblems" => :(using JuMP, Plots, QUBO),
    "8-OrderPartitioning" => :(using JuMP, Printf, QUBO),
    "9-CancerGenomics" => :(using DWave, JSON, JuMP, LinearAlgebra, Logging, Printf, QUBO),
    "10-QAOA" => :(using JuMP, QiskitOpt),
    "11-Annealing" => :(using DWave, JSON, JuMP, LinearAlgebra, Logging, Printf, QUBO),
)

timestamp() = Dates.format(now(), "HH:MM:SS")

function log_step(message::AbstractString)
    println("[$(timestamp())] $message")
    flush(stdout)
    return nothing
end

function detect_colab()
    return haskey(ENV, "COLAB_RELEASE_TAG") ||
        haskey(ENV, "COLAB_JUPYTER_IP") ||
        isdir(joinpath("/content", "sample_data"))
end

function env_bool(name::AbstractString)
    value = get(ENV, name, nothing)
    value === nothing && return nothing

    normalized = lowercase(strip(value))
    if normalized in ("1", "true", "yes", "on")
        return true
    elseif normalized in ("0", "false", "no", "off")
        return false
    end

    error("Expected `$name` to be one of 1/0/true/false/yes/no/on/off, got `$value`.")
end

default_bootstrap_warm_packages(; in_colab::Bool = detect_colab()) =
    something(env_bool("QUBONOTEBOOKS_WARM_PACKAGES"), false)

default_bootstrap_precompile(;
    in_colab::Bool = detect_colab(),
    warm_packages::Bool = default_bootstrap_warm_packages(in_colab = in_colab),
) = something(env_bool(PRECOMPILE_ENV), false)

function notebook_key(target::AbstractString)
    return splitext(basename(target))[1]
end

function notebook_requires_python(project_key::AbstractString)
    return project_key in PYTHON_STACK_NOTEBOOKS
end

notebook_import_expr(project_key::AbstractString) = get(NOTEBOOK_IMPORTS, project_key, nothing)

function notebook_project_dir(; repo_dir::AbstractString = WORKSPACE)
    return joinpath(repo_dir, NOTEBOOKS_DIRNAME)
end

function manifest_path(project_dir::AbstractString)
    return joinpath(project_dir, "Manifest.toml")
end

function manifest_julia_version(project_dir::AbstractString)
    path = manifest_path(project_dir)
    if !isfile(path)
        return nothing
    end

    manifest = TOML.parsefile(path)
    version_string = get(manifest, "julia_version", nothing)
    return version_string === nothing ? nothing : VersionNumber(version_string)
end

function requested_repo_ref()
    value = strip(get(ENV, REPO_REF_ENV, ""))
    return isempty(value) ? nothing : value
end

is_full_commit_sha(repo_ref::AbstractString) = occursin(r"^[0-9a-fA-F]{40}$", strip(repo_ref))

function repo_remote_url(repo_dir::AbstractString)
    return strip(readchomp(`git -C $repo_dir remote get-url origin`))
end

function resolve_repo_ref(repo_dir::AbstractString, repo_ref::AbstractString)
    remote_url = repo_remote_url(repo_dir)
    normalized_ref = strip(repo_ref)

    if is_full_commit_sha(normalized_ref)
        return (
            remote_url = remote_url,
            requested_sha = lowercase(normalized_ref),
            fetch_ref = normalized_ref,
            is_direct_sha = true,
        )
    end

    requested_ref = readchomp(`git ls-remote $remote_url $normalized_ref`)
    requested_sha = isempty(requested_ref) ? nothing : first(split(requested_ref))
    if requested_sha === nothing
        error("Could not resolve `$repo_ref` against `$remote_url`.")
    end

    return (
        remote_url = remote_url,
        requested_sha = lowercase(requested_sha),
        fetch_ref = normalized_ref,
        is_direct_sha = false,
    )
end

function checkout_repo_ref!(repo_dir::AbstractString, repo_ref::AbstractString)
    current_ref = lowercase(readchomp(`git -C $repo_dir rev-parse HEAD`))
    resolved = resolve_repo_ref(repo_dir, repo_ref)

    if current_ref == resolved.requested_sha
        return nothing
    end

    known_commit_cmd = Cmd([
        "git",
        "-C",
        repo_dir,
        "cat-file",
        "-e",
        "$(resolved.requested_sha)^{commit}",
    ])
    if resolved.is_direct_sha && success(known_commit_cmd)
        log_step("Checking out QUBONotebooks commit: $(resolved.requested_sha)")
        run(`git -C $repo_dir checkout --detach $(resolved.requested_sha)`)
        return nothing
    end

    log_step("Checking out QUBONotebooks ref: $repo_ref")
    run(`git -C $repo_dir fetch --depth 1 $(resolved.remote_url) $(resolved.fetch_ref)`)

    fetched_sha = lowercase(readchomp(`git -C $repo_dir rev-parse FETCH_HEAD`))
    if fetched_sha != resolved.requested_sha
        error("Resolved `$repo_ref` to $(resolved.requested_sha), but fetch from `$(resolved.remote_url)` produced $fetched_sha.")
    end

    run(`git -C $repo_dir checkout --detach $(resolved.requested_sha)`)
    return nothing
end

function validate_project_julia_version!(project_dir::AbstractString; in_colab::Bool = detect_colab())
    manifest_version = manifest_julia_version(project_dir)
    manifest_version === nothing && return nothing
    manifest_version == VERSION && return nothing

    configured_allow_mismatch = env_bool(ALLOW_VERSION_MISMATCH_ENV)
    allow_mismatch = something(configured_allow_mismatch, in_colab)
    message = "The Julia manifest at $(manifest_path(project_dir)) targets Julia $(manifest_version), but the current kernel is Julia $(VERSION)."

    if in_colab && !allow_mismatch
        error(message * " Set $(ALLOW_VERSION_MISMATCH_ENV)=1 to allow a slower re-resolve.")
    end

    reason = in_colab ? "Colab will allow Pkg to re-resolve the notebook environment" : "Colab mode is disabled"
    configured_allow_mismatch === true && (reason = "$(ALLOW_VERSION_MISMATCH_ENV)=1")
    @warn message * " Continuing because $reason."
    return nothing
end

function should_resolve_project_for_current_julia(project_dir::AbstractString; in_colab::Bool = detect_colab())
    manifest_version = manifest_julia_version(project_dir)
    return in_colab && manifest_version !== nothing && manifest_version != VERSION
end

active_stdlib_names() = Set(readdir(Base.load_path_expand("@stdlib")))

function strip_manifest_stdlib_pins!(project_dir::AbstractString; stdlib_names = active_stdlib_names())
    path = manifest_path(project_dir)
    isfile(path) || return false

    manifest = TOML.parsefile(path)
    deps = get(manifest, "deps", nothing)
    deps isa AbstractDict || return false

    changed = String[]
    for (name, entries) in deps
        name in stdlib_names || continue
        entries isa AbstractVector || continue

        for entry in entries
            entry isa AbstractDict || continue
            removed_pin = false
            if haskey(entry, "version")
                delete!(entry, "version")
                removed_pin = true
            end
            if haskey(entry, "git-tree-sha1")
                delete!(entry, "git-tree-sha1")
                removed_pin = true
            end
            removed_pin && push!(changed, String(name))
        end
    end

    isempty(changed) && return false

    log_step("Removing stale Julia stdlib pins before resolving: $(join(sort(unique(changed)), ", "))")
    open(path, "w") do io
        TOML.print(io, manifest, sorted = true)
    end
    return true
end

function resolve_project_for_current_julia!(project_dir::AbstractString; in_colab::Bool = detect_colab())
    should_resolve_project_for_current_julia(project_dir; in_colab = in_colab) || return false

    if in_colab
        get!(ENV, "JULIA_PKG_PRECOMPILE_AUTO", "0")
        strip_manifest_stdlib_pins!(project_dir)
    end
    log_step("Resolving Julia packages for current runtime Julia $(VERSION)")
    try
        Pkg.resolve()
    catch err
        if !in_colab
            rethrow()
        end

        @warn "Pkg.resolve() could not refresh $(manifest_path(project_dir)); updating Julia packages for current runtime Julia $(VERSION)." exception = (err, catch_backtrace())
        log_step("Updating Julia packages for current runtime Julia $(VERSION)")
        Pkg.update()
    end
    return true
end

function candidate_repo_dirs(; cwd::AbstractString = pwd())
    return unique((
        normpath(cwd),
        normpath(cwd, ".."),
        normpath(cwd, "QUBONotebooks"),
        normpath(cwd, "..", "QUBONotebooks"),
        normpath("/content", "QUBONotebooks"),
        WORKSPACE,
    ))
end

function is_repo_root(path::AbstractString)
    return isfile(joinpath(path, "scripts", "notebook_bootstrap.jl")) &&
        isdir(joinpath(path, NOTEBOOKS_DIRNAME))
end

function find_repo_root(; cwd::AbstractString = pwd())
    for candidate in candidate_repo_dirs(cwd = cwd)
        if is_repo_root(candidate)
            return normpath(candidate)
        end
    end
    return nothing
end

function ensure_repo_root(; in_colab::Bool = detect_colab())
    repo_dir = find_repo_root()
    repo_ref = requested_repo_ref()
    if repo_dir !== nothing
        if repo_ref !== nothing
            checkout_repo_ref!(repo_dir, repo_ref)
        end
        return repo_dir
    end

    if !in_colab
        error("Could not locate the QUBONotebooks repository root from $(pwd()).")
    end

    repo_dir = get(ENV, "QUBONOTEBOOKS_REPO_DIR", joinpath(pwd(), "QUBONotebooks"))
    if !isdir(repo_dir)
        log_step("Cloning JuliaQUBO/QUBONotebooks into $repo_dir")
        run(`git clone --depth 1 https://github.com/JuliaQUBO/QUBONotebooks.git $repo_dir`)
    else
        log_step("Using existing QUBONotebooks clone at $repo_dir")
    end

    if repo_ref !== nothing
        checkout_repo_ref!(repo_dir, repo_ref)
    end

    if !is_repo_root(repo_dir)
        error("The repository at $repo_dir does not contain the expected Julia notebook bootstrap files.")
    end

    ENV["QUBONOTEBOOKS_REPO_DIR"] = normpath(repo_dir)
    return normpath(repo_dir)
end

function configure_python_runtime!(
    repo_dir::AbstractString;
    in_colab::Bool = detect_colab(),
    python_packages::Vector{String} = ["dwave-ocean-sdk"],
)
    ENV["JULIA_CONDAPKG_BACKEND"] = "Null"

    if in_colab
        if !isempty(python_packages)
            log_step("Installing Python packages: $(join(python_packages, ", "))")
            run(`python3 -m pip install -q $(python_packages...)`)
        end
        python_exe = something(Sys.which("python3"), "python3")
    else
        python_exe = joinpath(repo_dir, ".venv", "bin", "python3")
        if !isfile(python_exe)
            error("Could not find $python_exe. Run `uv sync --group qubo` from the repository root before launching this notebook.")
        end
    end

    ENV["JULIA_PYTHONCALL_EXE"] = python_exe
    log_step("Using Python runtime: $python_exe")
    return python_exe
end

function activate_project!(project_dir::AbstractString)
    log_step("Activating project at `$project_dir`")
    Pkg.activate(project_dir)
    return nothing
end

function instantiate_project!(project_dir::AbstractString; precompile::Bool = true)
    activate_project!(project_dir)
    refreshed_for_current_julia = resolve_project_for_current_julia!(project_dir)
    log_step("Instantiating Julia packages")
    @time Pkg.instantiate()
    if precompile
        log_step("Precompiling Julia packages")
        @time Pkg.precompile()
    end
    return refreshed_for_current_julia
end

function warm_notebook_packages!(
    project_key::AbstractString;
    suppress_logs::Bool = true,
)
    import_expr = notebook_import_expr(project_key)
    import_expr === nothing && return false

    function load_packages()
        if project_key in CREDENTIAL_FREE_DWAVE_NOTEBOOKS
            return withenv("DWAVE_API_TOKEN" => nothing) do
                Core.eval(Main, import_expr)
            end
        end
        return Core.eval(Main, import_expr)
    end

    log_step("Loading notebook packages")
    if suppress_logs
        with_logger(NullLogger()) do
            load_packages()
        end
    else
        load_packages()
    end
    return true
end

function bootstrap_notebook(
    project_key::AbstractString;
    needs_python::Bool = notebook_requires_python(project_key),
    python_packages::Vector{String} = ["dwave-ocean-sdk"],
    warm_packages::Bool = default_bootstrap_warm_packages(),
    precompile::Bool = default_bootstrap_precompile(in_colab = detect_colab(), warm_packages = warm_packages),
    suppress_warmup_logs::Bool = warm_packages,
    chdir_to_notebooks::Bool = true,
)
    in_colab = detect_colab()
    repo_dir = ensure_repo_root(in_colab = in_colab)
    notebooks_dir = joinpath(repo_dir, NOTEBOOKS_DIRNAME)
    project_dir = notebook_project_dir(repo_dir = repo_dir)

    if !isdir(project_dir)
        error("Notebook project was not found at $project_dir.")
    end

    log_step("Notebook project key: $project_key")
    log_step("Google Colab runtime detected: $(in_colab)")
    if in_colab
        manifest_version = manifest_julia_version(project_dir)
        if manifest_version !== nothing
            log_step("Manifest Julia version: $(manifest_version)")
        end
    end
    validate_project_julia_version!(project_dir; in_colab = in_colab)

    if needs_python
        configure_python_runtime!(repo_dir; in_colab = in_colab, python_packages = python_packages)
    end

    refreshed_for_current_julia = instantiate_project!(project_dir; precompile = precompile)
    if warm_packages
        warm_notebook_packages!(project_key; suppress_logs = suppress_warmup_logs)
    end

    if chdir_to_notebooks
        cd(notebooks_dir)
        log_step("Working directory set to $notebooks_dir")
    end

    log_step("Notebook bootstrap complete")
    return (
        repo_dir = repo_dir,
        notebooks_dir = notebooks_dir,
        project_dir = project_dir,
        in_colab = in_colab,
    )
end

function instantiate_notebook_project(
    target::AbstractString;
    precompile::Bool = false,
    needs_python::Bool = notebook_requires_python(notebook_key(target)),
)
    project_key = notebook_key(target)
    repo_dir = ensure_repo_root(in_colab = false)
    project_dir = notebook_project_dir(repo_dir = repo_dir)

    if needs_python
        configure_python_runtime!(repo_dir; in_colab = false, python_packages = String[])
    end

    validate_project_julia_version!(project_dir; in_colab = false)
    instantiate_project!(project_dir; precompile = precompile)
    return project_dir
end

function instantiate_scripts_project(; precompile::Bool = false)
    repo_dir = ensure_repo_root(in_colab = false)
    project_dir = joinpath(repo_dir, "scripts")

    if !isdir(project_dir)
        error("Scripts project was not found at $project_dir.")
    end

    instantiate_project!(project_dir; precompile = precompile)
    return project_dir
end

end
