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


if __name__ == "__main__":
    unittest.main()
