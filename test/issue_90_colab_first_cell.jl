using Test

@testset "Issue 90 Colab first-cell setup" begin
    withenv(
        "COLAB_RELEASE_TAG" => "issue-90",
        "QUBONOTEBOOKS_WARM_PACKAGES" => nothing,
        "QUBONOTEBOOKS_PRECOMPILE" => nothing,
    ) do
        @test !QUBONotebooksBootstrap.default_bootstrap_warm_packages()
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

    @test QUBONotebooksBootstrap.default_python_packages("6-QCi") ==
        ["qci-client>=4.5,<6"]
    @test "qiskit>=2.3,<2.4" in
        QUBONotebooksBootstrap.default_python_packages("10-QAOA")
    @test QUBONotebooksBootstrap.default_python_packages("2-QUBO") ==
        ["dwave-ocean-sdk"]

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

        @test occursin(
            "QUBONotebooksBootstrap.bootstrap_notebook, \\\"$project_key\\\"",
            notebook,
        )
        @test occursin("\"id\": \"imports\"", notebook)
    end
end
