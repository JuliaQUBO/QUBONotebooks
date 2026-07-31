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


def stream(text: str, *, name: str = "stdout") -> dict:
    return {"name": name, "output_type": "stream", "text": [text]}


def clean_outputs() -> list[dict]:
    return [
        stream(
            "\n".join(
                [
                    "[12:00:00] Notebook project key: 7-CanonicalProblems",
                    "[12:00:00] Google Colab runtime detected: true",
                    "[12:00:00] Manifest Julia version: 1.12.6",
                    "[12:00:00] Instantiating Julia packages",
                    "[12:00:00] Loading notebook packages",
                    "[12:00:00] Notebook bootstrap complete",
                ]
            )
            + "\n"
        )
    ]


class ColabBootstrapSmokeTests(unittest.TestCase):
    def test_smoke_target_provides_colab_pip_without_locking_ocean(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text()
        target = makefile.split("verify-colab-bootstrap-output:", 1)[1].split(
            "\n\n", 1
        )[0]

        self.assertIn("--with pip", target)
        self.assertNotIn("--with dwave-ocean-sdk", target)

    def test_smoke_inventory_covers_every_julia_notebook(self) -> None:
        expected_paths = tuple(
            path.relative_to(REPO_ROOT)
            for path in sorted(
                (REPO_ROOT / "notebooks_jl").glob("*.ipynb"),
                key=lambda path: int(path.stem.split("-", 1)[0]),
            )
        )

        self.assertEqual(expected_paths, verify_colab_bootstrap.NOTEBOOK_PATHS)

    def test_extracts_real_bootstrap_cell(self) -> None:
        source = verify_colab_bootstrap.bootstrap_cell_source(REPO_ROOT)

        self.assertIn("function load_qubonotebooks_bootstrap()", source)
        self.assertIn(
            'bootstrap_notebook, "7-CanonicalProblems"',
            source,
        )
        self.assertTrue(source.rstrip().endswith("IN_COLAB = BOOTSTRAP.in_colab;"))

    def test_extracts_bootstrap_activation_and_import_cells(self) -> None:
        for notebook_path in verify_colab_bootstrap.NOTEBOOK_PATHS:
            with self.subTest(notebook=notebook_path.as_posix()):
                sources = verify_colab_bootstrap.smoke_cell_sources(
                    REPO_ROOT,
                    notebook_path,
                )

                self.assertIn(len(sources), (2, 3))
                self.assertIn("bootstrap_notebook", sources[0])
                self.assertIn("Pkg.instantiate", sources[1])
                self.assertIn("io = devnull", sources[1])
                if len(sources) == 3:
                    self.assertIn("using JuMP", sources[2])

    def test_accepts_only_concise_bootstrap_output(self) -> None:
        rendered = verify_colab_bootstrap.validate_bootstrap_outputs(clean_outputs())

        self.assertIn("Notebook bootstrap complete", rendered)

    def test_rejects_cell_errors(self) -> None:
        outputs = clean_outputs() + [
            {
                "ename": "MethodError",
                "evalue": "failed bootstrap",
                "output_type": "error",
                "traceback": ["large traceback intentionally ignored"],
            }
        ]

        with self.assertRaisesRegex(AssertionError, "cell error: MethodError"):
            verify_colab_bootstrap.validate_bootstrap_outputs(outputs)

    def test_rejects_execute_results_including_trailing_true(self) -> None:
        outputs = clean_outputs() + [
            {
                "data": {"text/plain": ["true"]},
                "execution_count": 1,
                "metadata": {},
                "output_type": "execute_result",
            }
        ]

        with self.assertRaisesRegex(AssertionError, "unexpected 'execute_result'"):
            verify_colab_bootstrap.validate_bootstrap_outputs(outputs)

    def test_rejects_each_noisy_output_class(self) -> None:
        noisy_samples = {
            "clone": "     Cloning git-repo https://github.com/example/package\n",
            "package": "   Installed Example ─ v1.2.3\n",
            "artifact": "  Installing 44 artifacts\n",
            "registry": "    Updating registry at `General.toml`\n",
            "manifest": "    Updating `/content/QUBONotebooks/Manifest.toml`\n",
            "pkg": "  Activating project at `/content/QUBONotebooks`\n",
            "precompile": "Precompiling packages...\n",
            "conda": "    CondaPkg Resolving changes\n",
            "mismatch": (
                "The Julia manifest targets Julia 1.10.11, but the "
                "current kernel is Julia 1.12.6.\n"
            ),
            "stacktrace": "Stacktrace:\n [1] example()\n",
            "task": "SYSTEM: caught exception of type :MethodError\n",
        }

        for label, text in noisy_samples.items():
            with self.subTest(label=label):
                with self.assertRaises(AssertionError):
                    verify_colab_bootstrap.validate_bootstrap_outputs(
                        clean_outputs() + [stream(text, name="stderr")]
                    )
