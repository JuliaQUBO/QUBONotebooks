"""Check the optional CUDA-Q CPU runtime, then execute selected notebooks."""

import math

import cudaq

import verify_notebooks


@cudaq.kernel
def bell_pair():
    q = cudaq.qvector(2)
    h(q[0])
    x.ctrl(q[0], q[1])


def main():
    """Fail if CPU simulation is unavailable or returns an incorrect Bell state."""
    cudaq.set_target("qpp-cpu")
    cudaq.set_random_seed(314159)
    counts = dict(cudaq.sample(bell_pair, shots_count=1024).items())
    assert set(counts) == {"00", "11"}, counts
    assert sum(counts.values()) == 1024, counts
    zz = cudaq.observe(bell_pair, cudaq.spin.z(0) * cudaq.spin.z(1)).expectation()
    z = cudaq.observe(bell_pair, cudaq.spin.z(0)).expectation()
    assert math.isclose(zz, 1.0, abs_tol=1e-12), zz
    assert math.isclose(z, 0.0, abs_tol=1e-12), z
    print(f"CUDA-Q qpp-cpu verified: Bell counts={counts}, <ZZ>={zz}, <Z>={z}", flush=True)
    return verify_notebooks.main()


if __name__ == "__main__":
    raise SystemExit(main())
