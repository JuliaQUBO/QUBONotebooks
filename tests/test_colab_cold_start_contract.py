from __future__ import annotations

import importlib.util
import inspect
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_colab_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("verify_colab_bootstrap", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
verify_colab_bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_colab_bootstrap)


def concise_bootstrap_output(*extra_lines: str) -> list[dict]:
    lines = [
        "[12:00:00] Notebook project key: 3-GAMA",
        "[12:00:00] Google Colab runtime detected: true",
        "[12:00:00] Manifest Julia version: 1.12.6",
        "[12:00:00] Activating project at `/content/QUBONotebooks/notebooks_jl/environments/3-GAMA`",
        "[12:00:00] Instantiating Julia packages",
        *extra_lines,
        "[12:00:00] Notebook bootstrap complete",
    ]
    return [
        {
            "name": "stdout",
            "output_type": "stream",
            "text": ["\n".join(lines) + "\n"],
        }
    ]


class ColabColdStartContractTests(unittest.TestCase):
    def test_readme_documents_deferred_package_loading(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text()

        self.assertIn(
            "Every notebook keeps package loading out of the default bootstrap",
            readme,
        )
        self.assertNotIn(
            "Notebooks 6 and 10 therefore perform one narrow",
            readme,
        )
        self.assertNotIn(
            "requires the narrow notebook 6 and 10 first-load workaround",
            readme,
        )

    def test_default_bootstrap_output_does_not_require_eager_warmup(self) -> None:
        rendered = verify_colab_bootstrap.validate_bootstrap_outputs(
            concise_bootstrap_output(),
            project_key="3-GAMA",
        )

        self.assertNotIn("Loading notebook packages", rendered)

    def test_rejects_eager_warmup_and_pip_progress(self) -> None:
        noisy_outputs = (
            ("Loading notebook packages", "eager package warm-up"),
            (
                "   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 8.7/8.7 MB",
                "pip download progress",
            ),
        )

        for output, expected_error in noisy_outputs:
            with self.subTest(output=output):
                with self.assertRaisesRegex(AssertionError, expected_error):
                    verify_colab_bootstrap.validate_bootstrap_outputs(
                        concise_bootstrap_output(output),
                        project_key="3-GAMA",
                    )

    def test_smoke_does_not_force_precompile_environment_override(self) -> None:
        main_source = inspect.getsource(verify_colab_bootstrap.main)
        forces_precompile_override = (
            '"JULIA_PKG_PRECOMPILE_AUTO": "0"' in main_source
        )

        self.assertFalse(forces_precompile_override)

    def test_post_bootstrap_cells_remain_error_checked(self) -> None:
        with self.assertRaisesRegex(AssertionError, "cell error: ErrorException"):
            verify_colab_bootstrap.validate_execution_outputs(
                [
                    {
                        "ename": "ErrorException",
                        "evalue": "deferred import failed",
                        "output_type": "error",
                        "traceback": ["large traceback intentionally ignored"],
                    }
                ]
            )

    def test_every_notebook_activation_disables_auto_precompile(self) -> None:
        missing_activation_guard = []
        duplicate_activation_guard = []
        for notebook_path in verify_colab_bootstrap.NOTEBOOK_PATHS:
            notebook = json.loads((REPO_ROOT / notebook_path).read_text())
            activation_source = verify_colab_bootstrap.activation_cell_source(
                REPO_ROOT,
                notebook_path,
            )
            guard_count = sum(
                "allow_autoprecomp = false" in "".join(cell.get("source", []))
                for cell in notebook["cells"]
            )

            if "allow_autoprecomp = false" not in activation_source:
                missing_activation_guard.append(notebook_path.as_posix())
            if guard_count != 1:
                duplicate_activation_guard.append(
                    (notebook_path.as_posix(), guard_count)
                )

        self.assertEqual(11, len(verify_colab_bootstrap.NOTEBOOK_PATHS))
        self.assertEqual([], missing_activation_guard)
        self.assertEqual([], duplicate_activation_guard)


if __name__ == "__main__":
    unittest.main()
