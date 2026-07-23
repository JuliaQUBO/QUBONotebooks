using Pkg; Pkg.instantiate()
using PackageCompiler, Libdl

const NOTEBOOKS_DIR = joinpath(@__DIR__, "..", "notebooks_jl")
const SYSIMAGE_PATH = joinpath(@__DIR__, "..", "sysimage", "sysimage.$(Libdl.dlext)")

mkpath(dirname(SYSIMAGE_PATH))

const PACKAGES = [
    # Misc
    "Graphs",
    "Karnak",
    "Luxor",
    "SpecialFunctions",

    # GAMA
    "BinaryWrappers",
    "lib4ti2_jll",
    "NPZ",

    # JuMP
    "AmplNLWriter",
    "Bonmin_jll",
    "Cbc",
    "Couenne_jll",
    "GLPK",
    "HiGHS",
    "Ipopt",
    "JuMP",

    # QUBO
    "DWave",
    "PythonCall",
    "QiskitOpt",
    "QUBO",

    # Visualization
    "Measures",
    "Plots",
    # "PythonPlot",
    "StatsBase",
    "StatsPlots",
]

PackageCompiler.create_sysimage(
    PACKAGES; 
    project       = NOTEBOOKS_DIR,
    sysimage_path = SYSIMAGE_PATH,
    cpu_target    = "generic;sandybridge,-xsaveopt,clone_all;haswell,-rdrnd,base(1)",
)
