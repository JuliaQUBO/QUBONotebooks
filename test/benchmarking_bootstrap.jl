"""Exercise the benchmark's real ensemble cell with small, local sample caches.

Energies are in arbitrary Ising units; read counts and performance ratios are
dimensionless. Constant-energy caches give hand-computed ratios of 1/2 and 1.
"""
module BenchmarkingBootstrapTests

using Test, JSON, Random, Statistics, LinearAlgebra, JuMP, QUBO, Plots
import DWave

const notebook = JSON.parsefile(joinpath(@__DIR__, "..", "notebooks_jl", "5-Benchmarking.ipynb"))

function cell_source(marker)
    sources = [join(cell["source"]) for cell in notebook["cells"] if cell["cell_type"] == "code"]
    return only(filter(source -> occursin(marker, source), sources))
end

# Use the notebook's reader, including its aggregation of repeated samples.
include_string(@__MODULE__, cell_source("function QUBOTools.read_solution"))
include_string(@__MODULE__, cell_source("function QUBOTools.write_solution"))
finite_or_inf_vec(raw_vec) = [(v isa Number && isfinite(v)) ? v : Inf for v in raw_vec]

primary_schedule = "geometric"
n = 3
instances = 0:1
sweeps = [10, 1000]
default_sweeps = 1000
min_median_index = 1
total_reads = 1000
all_results = Dict(
    i => Dict(
        :ttt => Dict(1000 => Dict("geometric" => (i == 0 ? [1.0, 2.0] : [2.0, 1.0]))), # seconds
        :min_energy => Dict("geometric" => -4.0),
        :random_energy => Dict("geometric" => 0.0),
    ) for i in instances
)

@testset "Julia ensemble bootstrap" begin
    mktempdir() do cache
        global pickle_path = cache
        for instance in instances, (sweep, energy) in ((10, -2.0), (1000, -4.0))
            # Real BQPJSON cache records, rather than a substitute sampler.
            sample = QUBOTools.Sample{Float64,Int}([1, 1, 1], energy, total_reads)
            samples = QUBOTools.SampleSet{Float64,Int}([sample]; domain = :spin)
            path = joinpath(cache, "solutions_$(instance)_geometric_$(sweep).json")
            open(path, "w") do io
                QUBOTools.write_solution(io, samples, QUBOTools.Format{:bqpjson}())
            end
        end

        include_string(@__MODULE__, cell_source("n_boot_plot = 100\n"))
        for instance in instances
            ratios = all_approx_ratio[instance]["geometric"]
            # Below, at, and above 100 repetitions, including the reported 999.
            for reads in (1, 100, 101, 999)
                @test ratios["10"][reads] == 0.5
                @test ratios["1000"][reads] == 1.0
            end
            # Julia's argmin is one-based; the two instances choose different sweeps.
            @test ratios["best"] == ratios[instance == 0 ? "10" : "1000"]
        end
    end

    mktempdir() do cache
        global pickle_path = cache
        global total_reads = 4
        include_string(@__MODULE__, cell_source("n_boot_plot = 100\n"))
        for instance in instances
            Random.seed!(instance)
            coupling = triu!(2rand(Float64, n, n) .- 1, 1)
            field = 2rand(Float64, n) .- 1
            for sweep in sweeps
                path = joinpath(cache, "solutions_$(instance)_geometric_$(sweep).json")
                samples = QUBOTools.read_solution(path)
                @test sum(QUBOTools.reads, samples) == total_reads
                for sample in samples
                    state = QUBOTools.state(sample)
                    # Evaluate in the original Ising model, in arbitrary energy units.
                    @test QUBOTools.value(sample) ≈ state' * coupling * state + field' * state
                end
            end
        end
        saved = Dict(name => read(joinpath(cache, name)) for name in readdir(cache))
        include_string(@__MODULE__, cell_source("n_boot_plot = 100\n"))
        @test saved == Dict(name => read(joinpath(cache, name)) for name in readdir(cache))
    end

end

end
