using Test

@testset "Issue 90 Colab first-cell setup" begin
    withenv(
        "COLAB_RELEASE_TAG" => "issue-90",
        "QUBONOTEBOOKS_WARM_PACKAGES" => nothing,
        "QUBONOTEBOOKS_PRECOMPILE" => nothing,
    ) do
        @test !QUBONotebooksBootstrap.default_bootstrap_warm_packages()
        for project_key in keys(QUBONotebooksBootstrap.NOTEBOOK_IMPORTS)
            @test QUBONotebooksBootstrap.default_bootstrap_warm_packages(
                project_key,
            )
        end
        @test !QUBONotebooksBootstrap.default_bootstrap_warm_packages("unknown")
        @test !QUBONotebooksBootstrap.default_bootstrap_precompile()
    end

    withenv(
        "COLAB_RELEASE_TAG" => "issue-90",
        "QUBONOTEBOOKS_WARM_PACKAGES" => "true",
        "QUBONOTEBOOKS_PRECOMPILE" => "true",
    ) do
        @test QUBONotebooksBootstrap.default_bootstrap_warm_packages()
        @test QUBONotebooksBootstrap.default_bootstrap_precompile()
    end

    @test !QUBONotebooksBootstrap.notebook_requires_python("6-QCi")
    @test !QUBONotebooksBootstrap.notebook_requires_python("10-QAOA")
    @test QUBONotebooksBootstrap.notebook_requires_python("2-QUBO")
    @test QUBONotebooksBootstrap.COLAB_SYSTEM_PYTHON_PACKAGES["6-QCi"] ==
        ["numpy", "requests"]
    @test QUBONotebooksBootstrap.python_import_statement(
        ["dwave-ocean-sdk"],
    ) == "import dwave"
    @test QUBONotebooksBootstrap.python_import_statement(
        ["numpy", "requests"],
    ) == "import numpy, requests"

    for project_key in keys(QUBONotebooksBootstrap.NOTEBOOK_IMPORTS)
        notebook = read(
            joinpath(repo_root, "notebooks_jl", "$project_key.ipynb"),
            String,
        )

        @test occursin(
            "QUBONotebooksBootstrap.bootstrap_notebook, \\\"$project_key\\\"",
            notebook,
        )
    end

    for project_key in (
        "6-QCi",
        "7-CanonicalProblems",
        "8-OrderPartitioning",
        "9-CancerGenomics",
        "10-QAOA",
        "11-Annealing",
    )
        notebook = read(
            joinpath(repo_root, "notebooks_jl", "$project_key.ipynb"),
            String,
        )
        @test occursin("\"id\": \"imports\"", notebook)
    end
end
