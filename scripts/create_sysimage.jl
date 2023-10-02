using Pkg; Pkg.instantiate()
using PackageCompiler, Libdl

const NOTEBOOKS_DIR = joinpath(@__DIR__, "..", "notebooks")
const SYSIMAGE_PATH = joinpath(@__DIR__, "..", "sysimage", "sysimage.$(Libdl.dlext)")

mkpath(dirname(SYSIMAGE_PATH))

const PACKAGES = [
    # Misc
    "Graphs",
    "Karnak",
    "SpecialFunctions",

    # GAMA
    "BinaryWrappers",
    "lib4ti2_jll",

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
    "QUBO",
    # "DWave",     # These use PythonCall!
    # "DWaveNeal",

    # Visualization
    # "Plots",
    "Measures",
    # "PythonCall",
    # "PythonPlot",
    "StatsBase",
    # "StatsPlots",
]

PackageCompiler.create_sysimage(
    PACKAGES; 
    project       = NOTEBOOKS_DIR,
    sysimage_path = SYSIMAGE_PATH,
    cpu_target    = "generic;sandybridge,-xsaveopt,clone_all;haswell,-rdrnd,base(1)",
)
