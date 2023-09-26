using Pkg; Pkg.instantiate()
using PackageCompiler, Libdl

const NOTEBOOKS_DIR = joinpath(@__DIR__, "..", "notebooks")
const SYSIMAGE_PATH = joinpath(@__DIR__, "..", "sysimage", "sysimage.$(Libdl.dlext)")

const PACKAGES = [
    # "AmplNLWriter",
    # "BinaryWrappers",
    # "Bonmin_jll",
    # "Cbc",
    # "Couenne_jll",
    # "DWave",
    # "DWaveNeal",
    # "GLPK",
    # "Graphs",
    # "HiGHS",
    # "Ipopt",
    # "JuMP",
    # "Karnak",
    # "Measures",
    "Plots",
    # "PythonCall",
    # "PythonPlot",
    # "QUBO",
    # "SpecialFunctions",
    # "StatsBase",
    # "StatsPlots",
    # "lib4ti2_jll",
]

PackageCompiler.create_sysimage(PACKAGES; project=NOTEBOOKS_DIR, sysimage_path=SYSIMAGE_PATH)
