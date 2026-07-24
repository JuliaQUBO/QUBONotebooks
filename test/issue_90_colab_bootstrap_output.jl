using Test

@testset "Issue 90 Colab bootstrap output" begin
    bootstrap_source = read(
        joinpath(repo_root, "scripts", "notebook_bootstrap.jl"),
        String,
    )

    registry_refresh = findfirst(
        "Pkg.Registry.update(; io = pkg_io, force = true)",
        bootstrap_source,
    )
    package_resolve = findfirst("Pkg.resolve(; io = pkg_io)", bootstrap_source)

    @test registry_refresh !== nothing
    @test package_resolve !== nothing
    @test occursin("git clone --quiet --depth 1", bootstrap_source)
    @test QUBONotebooksBootstrap.package_operation_io(true) === devnull
    @test QUBONotebooksBootstrap.package_operation_io(false) === stderr
    if registry_refresh !== nothing && package_resolve !== nothing
        @test first(registry_refresh) < first(package_resolve)
    end

    for operation in (
        "Pkg.activate(project_dir; io = pkg_io)",
        "Pkg.update(; io = pkg_io)",
        "Pkg.instantiate(; io = pkg_io)",
        "Pkg.precompile(; io = pkg_io)",
    )
        has_quiet_colab_operation = occursin(operation, bootstrap_source)
        @test has_quiet_colab_operation
    end

    for project_key in (
        "1-MathProg",
        "2-QUBO",
        "3-GAMA",
        "4-DWave",
        "5-Benchmarking",
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
        final_assignment = if project_key == "11-Annealing"
            "JULIA_PROJECT_DIR = BOOTSTRAP.project_dir;"
        else
            "IN_COLAB = BOOTSTRAP.in_colab;"
        end

        suppresses_bootstrap_result = occursin(final_assignment, notebook)
        uses_quiet_clone = occursin("git clone --quiet --depth 1", notebook) ||
            occursin(
                "\\\"git\\\", \\\"clone\\\", \\\"--quiet\\\", \\\"--depth\\\"",
                notebook,
            )
        @test suppresses_bootstrap_result
        @test uses_quiet_clone
    end
end
