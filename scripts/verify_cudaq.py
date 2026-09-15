"""Execute the required CUDA-Q QAOA and quantum-annealing sections."""

import json
import os
import sys
from pathlib import Path

import verify_notebooks


def require_optimization_result(notebook):
    """Require independent completion of both quantum methods in Lecture 4."""
    pending = {
        "cudaq-annealing-result": "CUDA-Q quantum annealing checks passed.",
        "cudaq-qaoa-results": "CUDA-Q QAOA checks passed.",
    }
    for cell in notebook["cells"]:
        if cell.get("execution_count") is None:
            continue
        text = "".join(
            "".join(output.get("text", []))
            for output in cell.get("outputs", [])
            if output.get("output_type") == "stream"
        )
        for tag in cell.get("metadata", {}).get("tags", []):
            if tag in pending and pending[tag] in text.splitlines():
                del pending[tag]
    if pending:
        raise RuntimeError("Incomplete CUDA-Q optimization sections: " + ", ".join(pending))


def main():
    """Run notebooks with CUDA-Q required and verify their optimization results."""
    os.environ["QUBONOTEBOOKS_CUDAQ_REQUIRE"] = "1"
    if len(sys.argv) == 1:
        sys.argv.append("notebooks_py/4-DWAVE_python.ipynb")
    args = verify_notebooks.parse_args()
    result = verify_notebooks.main()
    for name in args.notebooks:
        executed = verify_notebooks.output_dir() / Path(name).name
        require_optimization_result(json.loads(executed.read_text()))
    return result


if __name__ == "__main__":
    raise SystemExit(main())
