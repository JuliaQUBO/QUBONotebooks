using Test

@testset "Issue 90 Colab first-cell setup" begin
    withenv(
        "COLAB_RELEASE_TAG" => "issue-90",
        "QUBONOTEBOOKS_WARM_PACKAGES" => nothing,
        "QUBONOTEBOOKS_PRECOMPILE" => nothing,
    ) do
        @test !QUBONotebooksBootstrap.default_bootstrap_warm_packages()
        for project_key in keys(QUBONotebooksBootstrap.NOTEBOOK_IMPORTS)
            @test !QUBONotebooksBootstrap.default_bootstrap_warm_packages(
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
    qaoa_python_packages = [
        "qiskit~=2.3.0",
        "qiskit-aer~=0.17.0",
        "qiskit-ibm-runtime~=0.46.0",
        "qiskit-optimization~=0.7.0",
        "scipy~=1.15.0",
    ]
    @test get(
        QUBONotebooksBootstrap.COLAB_SYSTEM_PYTHON_PACKAGES,
        "6-QCi",
        nothing,
    ) == ["numpy", "requests"]
    @test get(
        QUBONotebooksBootstrap.COLAB_SYSTEM_PYTHON_PACKAGES,
        "9-CancerGenomics",
        nothing,
    ) == ["dwave-ocean-sdk"]
    @test get(
        QUBONotebooksBootstrap.COLAB_SYSTEM_PYTHON_PACKAGES,
        "10-QAOA",
        nothing,
    ) == qaoa_python_packages
    @test get(
        QUBONotebooksBootstrap.COLAB_SYSTEM_PYTHON_PACKAGES,
        "11-Annealing",
        nothing,
    ) == ["dwave-ocean-sdk"]
    @test QUBONotebooksBootstrap.python_import_statement(
        ["dwave-ocean-sdk"],
    ) == "import dwave"
    @test QUBONotebooksBootstrap.python_import_statement(
        ["numpy", "requests"],
    ) == "import numpy, requests"
    @test QUBONotebooksBootstrap.python_import_statement(
        qaoa_python_packages,
    ) ==
        "import qiskit, qiskit_aer, qiskit_ibm_runtime, qiskit_optimization, scipy"
    @test QUBONotebooksBootstrap.has_python_version_constraint("qiskit~=2.3.0")
    @test !QUBONotebooksBootstrap.has_python_version_constraint("requests")

    mktempdir() do project_dir
        preferences_path = joinpath(project_dir, "LocalPreferences.toml")
        write(preferences_path, "[Unrelated]\nkeep = true\n")
        returned_path =
            QUBONotebooksBootstrap.set_python_runtime_preferences!(
                project_dir,
                "/usr/bin/python3",
            )
        preferences = TOML.parsefile(preferences_path)

        @test returned_path == preferences_path
        @test preferences["PythonCall"]["exe"] == "/usr/bin/python3"
        @test preferences["CondaPkg"]["backend"] == "Null"
        @test preferences["Unrelated"]["keep"]
    end

    mktempdir() do repo_dir
        aggregate_project_dir = joinpath(repo_dir, "notebooks_jl")
        project_dir = joinpath(
            aggregate_project_dir,
            "environments",
            "10-QAOA",
        )
        mkpath(project_dir)
        withenv(
            "JULIA_CONDAPKG_BACKEND" => nothing,
            "JULIA_PYTHONCALL_EXE" => nothing,
        ) do
            python_exe = QUBONotebooksBootstrap.configure_python_runtime!(
                repo_dir;
                project_dir = project_dir,
                in_colab = true,
                python_packages = String[],
            )
            preferences = TOML.parsefile(
                joinpath(project_dir, "LocalPreferences.toml"),
            )

            @test ENV["JULIA_CONDAPKG_BACKEND"] == "Null"
            @test ENV["JULIA_PYTHONCALL_EXE"] == python_exe
            @test preferences["PythonCall"]["exe"] == python_exe
            @test preferences["CondaPkg"]["backend"] == "Null"
            @test !isfile(joinpath(aggregate_project_dir, "LocalPreferences.toml"))
        end
    end

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
