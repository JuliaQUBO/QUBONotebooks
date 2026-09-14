"""Execute the lecture's required CUDA-Q optimization section."""

import json
import os
import sys
from pathlib import Path

import verify_notebooks


def require_optimization_result(notebook):
    """Reject a skipped or missing optimization section in an executed notebook."""
    for cell in notebook["cells"]:
        if "cudaq-optimization-result" not in cell.get("metadata", {}).get("tags", []):
            continue
        text = "".join(
            "".join(output.get("text", []))
            for output in cell.get("outputs", [])
            if output.get("output_type") == "stream"
        )
        if cell.get("execution_count") is not None and "CUDA-Q optimization checks passed." in text.splitlines():
            return
    raise RuntimeError("The notebook did not complete its CUDA-Q optimization checks.")


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
