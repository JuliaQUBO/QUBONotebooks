using Test

repo_root = dirname(@__DIR__)

files_with_qubo_links = [
    "README.md",
    joinpath("templates", "qubo.ipynb"),
    joinpath("notebooks_jl", "2-QUBO.ipynb"),
    joinpath("notebooks_jl", "5-Benchmarking.ipynb"),
]
legacy_owners = ["psr" * "energy", "psr" * "nergy"]
notebook_links = [
    "notebooks_jl/1-MathProg.ipynb",
    "notebooks_py/1-MathProg_python.ipynb",
    "notebooks_jl/2-QUBO.ipynb",
    "notebooks_py/2-QUBO_python.ipynb",
    "notebooks_jl/3-GAMA.ipynb",
    "notebooks_py/3-GAMA_python.ipynb",
    "notebooks_jl/4-DWave.ipynb",
    "notebooks_py/4-DWAVE_python.ipynb",
    "notebooks_jl/5-Benchmarking.ipynb",
    "notebooks_py/5-Benchmarking_python.ipynb",
    "notebooks_py/6-QCi_python.ipynb",
]
files_with_repository_links = [
    "README.md",
    joinpath(".github", "workflows", "NOTES.md"),
    joinpath("templates", "julia.ipynb"),
    joinpath("templates", "qubo.ipynb"),
    joinpath("notebooks_jl", "4-DWave.ipynb"),
    joinpath("notebooks_py", "5-Benchmarking_python.ipynb"),
    joinpath("notebooks_py", "6-QCi_python.ipynb"),
]
stale_repository_links = [
    "pedromxavier/QUBO-notebooks",
    "AlbertLee125/QUBONotebooks",
    "SECQUOIA/QUBONotebooks",
]

@testset "QUBO.jl repository links" begin
    for file in files_with_qubo_links
        contents = read(joinpath(repo_root, file), String)

        for owner in legacy_owners
            @test !occursin("$owner/QUBO.jl", contents)
        end
    end

    readme = read(joinpath(repo_root, "README.md"), String)
    template = read(joinpath(repo_root, "templates", "qubo.ipynb"), String)

    @test occursin("https://github.com/JuliaQUBO/QUBO.jl", readme)
    @test occursin(
        "https://raw.githubusercontent.com/JuliaQUBO/QUBO.jl/main/docs/src/assets/logo.svg",
        readme,
    )
    @test occursin(
        "https://raw.githubusercontent.com/JuliaQUBO/QUBO.jl/main/docs/src/assets/logo.svg",
        template,
    )
end

@testset "README notebook links" begin
    readme = read(joinpath(repo_root, "README.md"), String)

    @test !occursin("(notebooks/", readme)
    @test occursin("make verify-python-portable", readme)
    @test occursin("make verify-gama-python", readme)

    for notebook in notebook_links
        @test occursin("($notebook)", readme)
        @test isfile(joinpath(repo_root, notebook))
    end
end

@testset "QUBONotebooks repository links" begin
    for file in files_with_repository_links
        contents = read(joinpath(repo_root, file), String)

        for stale_repository_link in stale_repository_links
            @test !occursin(stale_repository_link, contents)
        end
    end

    release_notes = read(joinpath(repo_root, ".github", "workflows", "NOTES.md"), String)
    @test occursin("https://github.com/JuliaQUBO/QUBONotebooks/releases/", release_notes)
end
