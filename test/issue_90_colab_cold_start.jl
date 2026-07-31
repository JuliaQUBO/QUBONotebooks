using Test

@testset "Issue 90 Colab cold-start policy" begin
    withenv(
        "COLAB_RELEASE_TAG" => "issue-90-cold-start",
        "QUBONOTEBOOKS_WARM_PACKAGES" => nothing,
    ) do
        for project_key in keys(QUBONotebooksBootstrap.NOTEBOOK_IMPORTS)
            @test !QUBONotebooksBootstrap.default_bootstrap_warm_packages(
                project_key,
            )
        end
    end

    withenv(
        "COLAB_RELEASE_TAG" => "issue-90-cold-start",
        "QUBONOTEBOOKS_WARM_PACKAGES" => "true",
    ) do
        @test QUBONotebooksBootstrap.default_bootstrap_warm_packages("3-GAMA")
    end

    bootstrap_source = read(
        joinpath(repo_root, "scripts", "notebook_bootstrap.jl"),
        String,
    )
    disables_bootstrap_auto_precompile = occursin(
        "Pkg.instantiate(; io = pkg_io, allow_autoprecomp = false)",
        bootstrap_source,
    )
    disables_pip_progress = occursin(
        "\"--progress-bar=off\"",
        bootstrap_source,
    )
    @test disables_bootstrap_auto_precompile
    @test disables_pip_progress

    notebooks_dir = joinpath(repo_root, "notebooks_jl")
    notebook_paths = filter(
        path -> endswith(path, ".ipynb"),
        readdir(notebooks_dir; join = true),
    )
    @test length(notebook_paths) == 11
    for notebook_path in notebook_paths
        notebook = read(notebook_path, String)
        disables_activation_auto_precompile = occursin(
            "Pkg.instantiate(; io = devnull, allow_autoprecomp = false)",
            notebook,
        )
        @test disables_activation_auto_precompile
    end
end
