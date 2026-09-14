"""Original CPU-only circuits for the issue #138 packaging/repeatability spike."""

import json
import math
from importlib.metadata import version

import cudaq
import numpy as np


@cudaq.kernel
def ghz():
    q = cudaq.qvector(4)
    h(q[0])
    for i in range(3):
        x.ctrl(q[i], q[i + 1])


@cudaq.kernel
def varied(angles: list[float]):
    q = cudaq.qvector(4)
    for i in range(4):
        ry(angles[i], q[i])
    x.ctrl(q[0], q[1])
    x.ctrl(q[2], q[3])


def run():
    """Check exact expectations and return canonical, seeded sample counts."""
    cudaq.set_target("qpp-cpu")
    cudaq.set_random_seed(314159)
    np.random.seed(314159)
    angles = np.random.uniform(0.2, 2.8, 4).tolist()
    ghz_counts = dict(cudaq.sample(ghz, shots_count=4096).items())
    assert set(ghz_counts) == {"0000", "1111"}, ghz_counts
    assert sum(ghz_counts.values()) == 4096
    assert abs(ghz_counts["0000"] / 4096 - 0.5) < 0.05
    zz = cudaq.spin.z(0) * cudaq.spin.z(1)
    observed = cudaq.observe(varied, zz, angles).expectation()
    # Conjugating Z0 Z1 by CNOT(0, 1) gives Z1; <Z1> = cos(theta1).
    assert math.isclose(observed, math.cos(angles[1]), abs_tol=1e-12)
    varied_counts = dict(cudaq.sample(varied, angles, shots_count=4096).items())
    assert sum(varied_counts.values()) == 4096
    assert len(varied_counts) > 2
    result = {
        "cudaq_version": version("cuda-quantum-cu13"),
        "numpy_version": np.__version__,
        "target": cudaq.get_target().name,
        "seed": 314159,
        "shots": 4096,
        "angles": angles,
        "ghz_counts": ghz_counts,
        "varied_counts": varied_counts,
        "expected_zz": math.cos(angles[1]),
        "observed_zz": observed,
    }
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    run()
