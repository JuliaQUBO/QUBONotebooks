from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "verify_colab_bootstrap.py"
SPEC = importlib.util.spec_from_file_location("verify_colab_bootstrap", MODULE_PATH)
assert SPEC is not None
assert SPEC.loader is not None
verify_colab_bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify_colab_bootstrap)

HOSTED_MODULE_PATH = REPO_ROOT / "scripts" / "verify_hosted_colab.py"
HOSTED_SPEC = importlib.util.spec_from_file_location(
    "verify_hosted_colab",
    HOSTED_MODULE_PATH,
)
assert HOSTED_SPEC is not None
assert HOSTED_SPEC.loader is not None
verify_hosted_colab = importlib.util.module_from_spec(HOSTED_SPEC)
HOSTED_SPEC.loader.exec_module(verify_hosted_colab)


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

    def test_hosted_target_uses_a_fresh_auto_released_colab_vm(self) -> None:
        command = verify_hosted_colab.colab_run_command(
            script_path=HOSTED_MODULE_PATH,
            auth="oauth2",
            timeout=3600,
            repo_ref="a" * 40,
            repo_url="https://github.com/JuliaQUBO/QUBONotebooks.git",
            notebooks="11-Annealing",
        )

        self.assertIn("run", command)
        self.assertNotIn("exec", command)
        self.assertNotIn("--keep", command)
        self.assertIn("QUBONOTEBOOKS_HOSTED_COLAB_RUNNER=checkout", command)
        self.assertIn(f"QUBONOTEBOOKS_REPO_REF={'a' * 40}", command)

    def test_hosted_runner_loads_when_colab_does_not_define_file(self) -> None:
        source = HOSTED_MODULE_PATH.read_text()
        program = (
            f"exec(compile({source!r}, '<colab-cell>', 'exec'), "
            "{'__name__': 'colab_cell'})\n"
        )

        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=REPO_ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_hosted_checkout_calls_exact_ref_module_in_process(self) -> None:
        source = HOSTED_MODULE_PATH.read_text()

        self.assertIn("hosted_module = load_hosted_module(checkout)", source)
        self.assertIn(
            "hosted_module.hosted_verify_main(repo_root=checkout, env=env)",
            source,
        )
        self.assertNotIn(
            '[sys.executable, str(checkout / "scripts" / "verify_hosted_colab.py")]',
            source,
        )

    def test_hosted_cell_timing_uses_iopub_lifecycle(self) -> None:
        cell = {
            "id": "bootstrap",
            "metadata": {
                "execution": {
                    "iopub.execute_input": "2026-07-31T14:52:35.000000Z",
                    "iopub.status.idle": "2026-07-31T14:53:08.250000Z",
                    "shell.execute_reply": "2026-07-31T14:53:08.000000Z",
                }
            },
        }

        self.assertEqual(33.25, verify_hosted_colab.cell_elapsed_seconds(cell))

    def test_notebook_11_keeps_dwave_loading_out_of_bootstrap(self) -> None:
        notebook_path = Path("notebooks_jl/11-Annealing.ipynb")
        sources = verify_colab_bootstrap.smoke_cell_sources(
            REPO_ROOT,
            notebook_path,
        )

        self.assertIn("warm_notebook_packages!", sources[2])
        self.assertIn('"11-Annealing"', sources[2])

    def test_smoke_inventory_covers_every_julia_notebook(self) -> None:
        expected_paths = tuple(
            path.relative_to(REPO_ROOT)
            for path in sorted(
                (REPO_ROOT / "notebooks_jl").glob("*.ipynb"),
                key=lambda path: int(path.stem.split("-", 1)[0]),
            )
        )

        self.assertEqual(expected_paths, verify_colab_bootstrap.NOTEBOOK_PATHS)

    def test_smoke_can_select_one_or_more_notebooks(self) -> None:
        selected = verify_colab_bootstrap.selected_notebook_paths(
            "11-Annealing, 9-CancerGenomics"
        )

        self.assertEqual(
            (
                Path("notebooks_jl/11-Annealing.ipynb"),
                Path("notebooks_jl/9-CancerGenomics.ipynb"),
            ),
            selected,
        )

    def test_smoke_rejects_unknown_notebook_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown Julia notebook key"):
            verify_colab_bootstrap.selected_notebook_paths("1-MathProg,12-Unknown")

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

                self.assertEqual(3, len(sources))
                self.assertIn("bootstrap_notebook", sources[0])
                self.assertIn("Pkg.instantiate", sources[1])
                self.assertIn("io = devnull", sources[1])
                self.assertIn("warm_notebook_packages!", sources[2])
                self.assertIn(f'"{notebook_path.stem}"', sources[2])

    def test_explicit_import_cells_use_the_quiet_shared_loader(self) -> None:
        for notebook_path in verify_colab_bootstrap.NOTEBOOK_PATHS:
            data = verify_colab_bootstrap.json.loads(
                (REPO_ROOT / notebook_path).read_text()
            )
            import_cells = [
                cell for cell in data["cells"] if cell.get("id") == "imports"
            ]
            if not import_cells:
                continue

            with self.subTest(notebook=notebook_path.as_posix()):
                source = verify_colab_bootstrap.text_value(import_cells[0]["source"])
                self.assertIn("Base.invokelatest", source)
                self.assertIn("warm_notebook_packages!", source)
                self.assertIn(f'"{notebook_path.stem}"', source)
                self.assertIn("suppress_logs = true", source)

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

    def test_notebook_validation_identifies_the_failing_cell(self) -> None:
        cells = [
            {"id": "bootstrap", "outputs": clean_outputs()},
            {
                "id": "imports",
                "outputs": [stream("SYSTEM: caught exception\n", name="stderr")],
            },
        ]

        with self.assertRaisesRegex(AssertionError, r"cell 2 \(imports\)"):
            verify_colab_bootstrap.validate_notebook_execution(cells)

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
