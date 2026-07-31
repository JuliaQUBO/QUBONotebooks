import Pkg

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

for project_key in sort!(collect(keys(QUBONotebooksBootstrap.NOTEBOOK_IMPORTS)))
    project_dir = QUBONotebooksBootstrap.notebook_project_dir(
        project_key;
        repo_dir = REPO_ROOT,
    )
    destination_manifest = joinpath(project_dir, basename(SOURCE_MANIFEST))
    cp(SOURCE_MANIFEST, destination_manifest; force = true)
    Pkg.activate(project_dir)
    Pkg.resolve()
end

Pkg.activate(AGGREGATE_PROJECT)
