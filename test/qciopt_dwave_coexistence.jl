using Test
using JuMP
using QCIOpt
using DWave

@testset "QCIOpt and DWave default CondaPkg coexistence" begin
    @test !haskey(ENV, "JULIA_CONDAPKG_BACKEND")
    @test !haskey(ENV, "JULIA_PYTHONCALL_EXE")
    @test QCIOpt.Optimizer <: JuMP.MOI.AbstractOptimizer
    @test DWave.Optimizer <: JuMP.MOI.AbstractOptimizer

    networkx_version = QCIOpt.PythonCall.pyconvert(
        String,
        QCIOpt.PythonCall.pyimport("networkx").__version__,
    )
    @test VersionNumber(networkx_version).major == 3
    @test QCIOpt.PythonCall.pyconvert(String, QCIOpt.qcic.__name__) ==
        "qciopt_client"
    @test QCIOpt.PythonCall.pyconvert(
        Any,
        QCIOpt.PythonCall.pyimport("importlib.util").find_spec("qci_client"),
    ) === nothing

    @test QCIOpt.qci_default_token() === nothing
    model = Model(QCIOpt.Optimizer)
    @variable(model, x[1:3], Bin)
    @objective(model, Min, (sum(x) - 1)^2)
    @test num_variables(model) == 3

    println(
        "QCIOpt + DWave coexist with NetworkX $networkx_version and no QCI credentials.",
    )
end
