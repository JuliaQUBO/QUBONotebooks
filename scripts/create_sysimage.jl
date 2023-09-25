using Pkg; Pkg.instantiate()
using PackageCompiler, Libdl

const NOTEBOOKS_DIR = joinpath(@__DIR__, "..", "notebooks")
const SYSIMAGE_PATH = joinpath(@__DIR__, "..", "sysimage", "sysimage.$(Libdl.dlext)")

PackageCompiler.create_sysimage(; project=NOTEBOOKS_DIR, sysimage_path=SYSIMAGE_PATH)
