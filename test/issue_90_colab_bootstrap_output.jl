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
    redirects_colab_package_stderr =
        occursin("redirect_stderr(devnull)", bootstrap_source)
    @test redirects_colab_package_stderr
    if registry_refresh !== nothing && package_resolve !== nothing
        @test first(registry_refresh) < first(package_resolve)
    end

    mktemp() do _, io
        redirect_stderr(io) do
            QUBONotebooksBootstrap.with_package_operation_io(true) do pkg_io
                @test pkg_io === devnull
                println(stderr, "hidden Colab package progress")
            end
        end
        flush(io)
        seekstart(io)
        @test isempty(read(io, String))
    end

    mktemp() do _, stdout_io
        mktemp() do _, stderr_io
            redirect_stdout(stdout_io) do
                redirect_stderr(stderr_io) do
                    QUBONotebooksBootstrap.with_suppressed_output() do
                        println(stdout, "hidden package stdout")
                        println(stderr, "hidden package stderr")
                        @info "hidden package log"
                    end
                end
            end
            flush(stdout_io)
            flush(stderr_io)
            seekstart(stdout_io)
            seekstart(stderr_io)
            @test isempty(read(stdout_io, String))
            @test isempty(read(stderr_io, String))
        end
    end

    mktemp() do _, stdout_io
        mktemp() do _, stderr_io
            loaded = redirect_stdout(stdout_io) do
                redirect_stderr(stderr_io) do
                    Base.invokelatest(
                        QUBONotebooksBootstrap.load_notebook_packages!,
                        "test packages",
                        :(begin
                            println(stdout, "hidden import stdout")
                            println(stderr, "hidden import stderr")
                            @info "hidden import log"
                            17
                        end);
                        suppress_logs = true,
                    )
                end
            end
            flush(stdout_io)
            flush(stderr_io)
            seekstart(stdout_io)
            seekstart(stderr_io)
            captured_stdout = read(stdout_io, String)
            captured_stderr = read(stderr_io, String)

            @test loaded === true
            @test occursin("Loading test packages", captured_stdout)
            @test !occursin("hidden import", captured_stdout)
            @test isempty(captured_stderr)
        end
    end

    @test_throws ErrorException Base.invokelatest(
        QUBONotebooksBootstrap.load_notebook_packages!,
        "failing test package",
        :(error("import failure must propagate"));
        suppress_logs = true,
    )

    for operation in (
        "Pkg.activate(project_dir; io = pkg_io)",
        "Pkg.update(; io = pkg_io)",
        "Pkg.instantiate(; io = pkg_io, allow_autoprecomp = false)",
        "Pkg.precompile(; io = pkg_io)",
    )
        has_quiet_colab_operation = occursin(operation, bootstrap_source)
        @test has_quiet_colab_operation
    end

    notebooks_dir = joinpath(repo_root, "notebooks_jl")
    notebook_paths = sort(filter(
        path -> endswith(path, ".ipynb"),
        readdir(notebooks_dir; join = true),
    ))
    project_keys = [
        splitext(basename(notebook_path))[1] for notebook_path in notebook_paths
    ]

    @test !isempty(notebook_paths)
    @test "6-QCi" in project_keys

    for (project_key, notebook_path) in zip(project_keys, notebook_paths)
        notebook = read(notebook_path, String)
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

        @testset "$project_key" begin
            @test suppresses_bootstrap_result
            @test uses_quiet_clone
        end
    end
end
