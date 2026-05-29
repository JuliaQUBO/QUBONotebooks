using Test

repo_root = dirname(@__DIR__)

files_with_qubo_links = [
    "README.md",
    joinpath("templates", "qubo.ipynb"),
    joinpath("notebooks_jl", "2-QUBO.ipynb"),
    joinpath("notebooks_jl", "5-Benchmarking.ipynb"),
]
legacy_owners = ["psr" * "energy", "psr" * "nergy"]

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
