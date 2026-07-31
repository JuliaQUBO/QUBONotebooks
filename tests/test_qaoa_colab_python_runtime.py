from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_colab_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("verify_colab_bootstrap", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
verify_colab_bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_colab_bootstrap)


def stream(text: str) -> dict:
    return {"name": "stderr", "output_type": "stream", "text": [text]}


def qaoa_bootstrap_outputs(*, warm_packages: bool = False) -> list[dict]:
    lines = [
        "[12:00:00] Notebook project key: 10-QAOA",
        "[12:00:00] Google Colab runtime detected: true",
        "[12:00:00] Manifest Julia version: 1.12.6",
        "[12:00:00] Instantiating Julia packages",
    ]
    if warm_packages:
        lines.append("[12:00:00] Loading notebook packages")
    lines.append("[12:00:00] Notebook bootstrap complete")
    return [stream("\n".join(lines) + "\n")]


class QAOAColabPythonRuntimeTests(unittest.TestCase):
    def test_rejects_condapkg_setup_from_deferred_import_cells(self) -> None:
        environment_setup_samples = (
            "    CondaPkg Resolving changes\n",
            " Downloading artifact: micromamba\n",
            " Downloading artifact: pixi\n",
            "             └ /content/QUBONotebooks/notebooks_jl/.CondaPkg\n",
            "✔ Created /content/QUBONotebooks/notebooks_jl/.CondaPkg/pixi.toml\n",
        )

        for output in environment_setup_samples:
            with self.subTest(output=output):
                with self.assertRaisesRegex(
                    AssertionError,
                    "CondaPkg environment setup",
                ):
                    verify_colab_bootstrap.validate_execution_outputs(
                        [stream(output)]
                    )

    def test_qaoa_defers_package_loading_to_its_quiet_import_cell(self) -> None:
        rendered = verify_colab_bootstrap.validate_bootstrap_outputs(
            qaoa_bootstrap_outputs(),
            project_key="10-QAOA",
        )

        self.assertNotIn("Loading notebook packages", rendered)
        with self.assertRaisesRegex(AssertionError, "eager package warm-up"):
            verify_colab_bootstrap.validate_bootstrap_outputs(
                qaoa_bootstrap_outputs(warm_packages=True),
                project_key="10-QAOA",
            )


if __name__ == "__main__":
    unittest.main()
