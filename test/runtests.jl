using Test
import TOML

repo_root = dirname(@__DIR__)
include(joinpath(repo_root, "scripts", "notebook_bootstrap.jl"))

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
    "notebooks_jl/7-CanonicalProblems.ipynb",
    "notebooks_jl/8-OrderPartitioning.ipynb",
    "notebooks_jl/9-CancerGenomics.ipynb",
    "notebooks_jl/10-QAOA.ipynb",
    "notebooks_jl/11-Annealing.ipynb",
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
gama_notebook_path = joinpath(repo_root, "notebooks_jl", "3-GAMA.ipynb")

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

@testset "Julia GAMA notebook execution guards" begin
    contents = replace(
        read(gama_notebook_path, String),
        "\r\n" => "\n",
        "\\u03b5" => "ε",
        "\\u03bc" => "μ",
        "\\u03c3" => "σ",
    )

    @test occursin("const ε_default = 0.01", contents)
    @test occursin("function f(x; μ=μ_default, σ=σ_default, ε=ε_default)", contents)
    @test occursin("ε = ε_default", contents)
    @test !occursin("μ = rand(n)", contents)
    @test !occursin("σ = rand(n) .* μ", contents)

    @test occursin("GRAVER_BASIS_URL", contents)
    @test occursin("https://github.com/JuliaQUBO/QUBONotebooks/raw/main/notebooks_jl/graver.npy", contents)
    @test occursin("Downloads.download(GRAVER_BASIS_URL, download_path)", contents)
    @test isfile(joinpath(repo_root, "notebooks_jl", "graver.npy"))

    @test !occursin("using JuMP, DWave, LinearAlgebra", contents)
    @test occursin("const HAS_DWAVE = try", contents)
    @test occursin("function load_precomputed_feasible_starts()", contents)
    @test occursin("DWave.jl is unavailable; loaded", contents)
    @test isfile(joinpath(repo_root, "notebooks_data", "3-GAMA_example4_feasible_starts.csv"))

    @test occursin("gprev = fill(typemin(Int), n)", contents)
    @test !occursin("gprev = Vector{Int}(undef, n)", contents)
end

@testset "Julia Colab stdlib manifest sanitization" begin
    mktempdir() do dir
        project_dir = joinpath(dir, "notebooks_jl")
        mkpath(project_dir)
        manifest = joinpath(project_dir, "Manifest.toml")

        write(
            manifest,
            """
            julia_version = "1.10.11"
            manifest_format = "2.0"

            [[deps.ExamplePackage]]
            git-tree-sha1 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            uuid = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
            version = "1.2.3"

            [[deps.Statistics]]
            deps = ["LinearAlgebra", "SparseArrays"]
            git-tree-sha1 = "cccccccccccccccccccccccccccccccccccccccc"
            uuid = "10745b16-79ce-11e8-11f9-7d13ad32a3b2"
            version = "1.10.0"
            """,
        )

        @test QUBONotebooksBootstrap.strip_manifest_stdlib_pins!(project_dir)

        parsed = TOML.parsefile(manifest)
        statistics_entry = only(parsed["deps"]["Statistics"])
        package_entry = only(parsed["deps"]["ExamplePackage"])

        @test !haskey(statistics_entry, "version")
        @test !haskey(statistics_entry, "git-tree-sha1")
        @test package_entry["version"] == "1.2.3"
        @test package_entry["git-tree-sha1"] == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        @test !QUBONotebooksBootstrap.strip_manifest_stdlib_pins!(project_dir)
    end
end
