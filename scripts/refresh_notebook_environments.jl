import Pkg
import TOML

include(joinpath(@__DIR__, "notebook_bootstrap.jl"))
using .QUBONotebooksBootstrap

const REPO_ROOT = normpath(joinpath(@__DIR__, ".."))
const AGGREGATE_PROJECT = QUBONotebooksBootstrap.aggregate_notebook_project_dir(
    repo_dir = REPO_ROOT,
)
const SOURCE_MANIFEST = QUBONotebooksBootstrap.manifest_path(
    AGGREGATE_PROJECT;
    julia_version = VERSION,
)

isfile(SOURCE_MANIFEST) || error(
    "No aggregate manifest for Julia $(VERSION.major).$(VERSION.minor): " *
    SOURCE_MANIFEST,
)

project_keys = isempty(ARGS) ? sort!(collect(keys(QUBONotebooksBootstrap.NOTEBOOK_IMPORTS))) : ARGS
all(key -> haskey(QUBONotebooksBootstrap.NOTEBOOK_IMPORTS, key), project_keys) ||
    error("Unknown notebook project key")

for project_key in project_keys
    project_dir = QUBONotebooksBootstrap.notebook_project_dir(
        project_key;
        repo_dir = REPO_ROOT,
    )
    destination_manifest = joinpath(project_dir, basename(SOURCE_MANIFEST))
    project = TOML.parsefile(joinpath(project_dir, "Project.toml"))
    sources = get(project, "sources", Dict())
    if isempty(sources)
        cp(SOURCE_MANIFEST, destination_manifest; force = true)
    elseif !isfile(destination_manifest)
        # Seed a new runtime lock from this focused project's existing lock,
        # preserving source provenance instead of importing the aggregate graph.
        focused_manifest = joinpath(project_dir, "Manifest.toml")
        isfile(focused_manifest) || error("Generate the Julia 1.10 source lock first")
        cp(focused_manifest, destination_manifest)
        QUBONotebooksBootstrap.strip_manifest_stdlib_pins!(project_dir)
    end
    Pkg.activate(project_dir)
    for (name, source) in sources
        # Pkg's [sources] support is newer than Julia 1.10. Make the same
        # immutable source declaration explicit to both supported runtimes.
        haskey(source, "path") && error("Notebook sources must not use local paths")
        QUBONotebooksBootstrap.is_full_commit_sha(source["rev"]) ||
            error("Notebook source revisions must be full commit SHAs")
        Pkg.add(Pkg.PackageSpec(name = name, url = source["url"], rev = source["rev"]))
    end
    Pkg.resolve()
end

Pkg.activate(AGGREGATE_PROJECT)
