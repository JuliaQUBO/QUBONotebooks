"""Derived book and notebook structure contracts."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from notebook_test_support import (
    REPO_ROOT,
    is_notebook_footer,
    notebook_cells,
    notebook_first_heading,
    notebook_markdown,
    notebook_paths,
)


class JupyterBookConfigurationTests(unittest.TestCase):
    def test_notebook_headers_match_toc_titles_and_share_one_format(self) -> None:
        """JB2 titles and the visible notebook masthead have one contract."""
        myst_source = (REPO_ROOT / "myst.yml").read_text()
        toc_titles = dict(
            re.findall(
                r"^\s*-\s+file:\s+([^\s#]+\.ipynb)\s*\n\s+title:\s+(.+?)\s*$",
                myst_source,
                flags=re.MULTILINE,
            )
        )

        self.assertEqual(len(notebook_paths()), len(toc_titles))

        for path in notebook_paths():
            relative_path = path.relative_to(REPO_ROOT).as_posix()
            with self.subTest(notebook=relative_path):
                first_cell = notebook_cells(path)[0]
                source = "".join(first_cell.get("source", []))
                markdown_h1s = re.findall(r"^#\s+(.+?)\s*$", source, re.MULTILINE)
                anchor_match = re.match(r'<div id="([^"]+)"></div>', source)

                self.assertEqual("markdown", first_cell.get("cell_type"))
                self.assertEqual([toc_titles[relative_path]], markdown_h1s)
                self.assertNotIn("<h1", source.lower())
                self.assertIsNotNone(anchor_match)

                anchor = anchor_match.group(1)
                expected_header = (
                    f'<div id="{anchor}"></div>\n'
                    "\n"
                    f"# {toc_titles[relative_path]}\n"
                    "\n"
                    '<div align="center">\n'
                    '    <b>Maintained by the <a href="https://github.com/JuliaQUBO">JuliaQUBO</a> organization</b>\n'
                    "    <br>\n"
                    '    <a href="https://secquoia.github.io/">SECQUOIA</a> &nbsp;&middot;&nbsp; <a href="https://www.psr-inc.com/">PSR Energy</a>\n'
                    "    <br>\n"
                    "    <br>\n"
                    f'    <a href="https://colab.research.google.com/github/JuliaQUBO/QUBONotebooks/blob/main/{relative_path}" target="_parent">\n'
                    '        <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/>\n'
                    "    </a>\n"
                    "</div>"
                )
                self.assertTrue(source.startswith(expected_header))

    def test_book_build_gate_is_configured_as_intended(self) -> None:
        """The book build is a merge gate, so its policy is asserted in one place.

        Each setting below is silent if reverted: the build still succeeds, so
        only this test would notice the gate weakening.
        """
        # Defect class: a configuration edit silently weakens the repository-
        # owned strict build gate or makes third-party availability fatal.
        workflow = (REPO_ROOT / ".github" / "workflows" / "jupyter-book.yml").read_text()
        makefile = (REPO_ROOT / "Makefile").read_text()
        severities = dict(
            re.findall(
                r"-\s+id:\s+([a-z0-9-]+)\s*\n\s+severity:\s+([a-z]+)",
                (REPO_ROOT / "myst.yml").read_text(),
            )
        )

        # Strict mode is what turns the build into a gate at all.
        self.assertIn("jupyter book build --html --ci --strict", makefile)
        # ...but reaching third-party hosts must not decide whether a merge passes.
        self.assertEqual("warn", severities.get("link-resolves"))
        self.assertEqual("warn", severities.get("doi-link-valid"))
        self.assertEqual("error", severities.get("reference-target-resolves"))
        # A cancelled deploy can leave Pages half-published.
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            workflow,
        )
        # Jupyter Book 2 reads myst.yml; the JB1 files must stay deleted.
        self.assertFalse((REPO_ROOT / "_config.yml").exists())
        self.assertFalse((REPO_ROOT / "requirements-book.txt").exists())
        self.assertIn("uv sync --locked --group docs", workflow)

    def test_colab_map_covers_every_toc_notebook_route(self) -> None:
        myst_source = (REPO_ROOT / "myst.yml").read_text()
        colab_source = (REPO_ROOT / "colab.html").read_text()
        toc_notebooks = re.findall(
            r"^\s*-\s+file:\s+([^\s#]+\.ipynb)\s*$",
            myst_source,
            flags=re.MULTILINE,
        )
        map_entries = re.findall(
            r'^\s*"([^"]+)":\s*"([^"]+\.ipynb)",?\s*$',
            colab_source,
            flags=re.MULTILINE,
        )
        colab_map = dict(map_entries)

        self.assertTrue(toc_notebooks)
        self.assertEqual(len(map_entries), len(colab_map), "duplicate Colab route key")
        self.assertEqual(set(toc_notebooks), set(colab_map.values()))

        for notebook in toc_notebooks:
            with self.subTest(notebook=notebook):
                path = Path(notebook)
                directory = path.parent.as_posix().replace("_", "-").lower()
                slug = re.sub(r"^\d+-", "", path.stem).replace("_", "-").lower()
                slash_route = f"{directory}/{slug}"
                dot_route = slash_route.replace("/", ".")

                self.assertEqual(notebook, colab_map.get(slash_route))
                self.assertEqual(notebook, colab_map.get(dot_route))
                self.assertTrue((REPO_ROOT / notebook).is_file())

    def test_notebook_footer_helper_accepts_only_real_footers(self) -> None:
        accepted = {
            "acknowledgments": {
                "cell_type": "markdown",
                "source": ["## Acknowledgments\n", "\n", "- [Someone](https://github.com/x)\n"],
            },
            "back to top": {
                "cell_type": "markdown",
                "source": [
                    '<div align="center">\n',
                    '    <a href="#top-jl-2-qubo">\U0001f51d Go back to the top \U0001f51d</a>\n',
                    "</div>",
                ],
            },
        }
        rejected = {
            "code cell printing the phrase": {
                "cell_type": "code",
                "source": ['print("\U0001f51d Go back to the top \U0001f51d")\n'],
            },
            "lesson prose mentioning the phrase": {
                "cell_type": "markdown",
                "source": ["Scroll up and Go back to the top of the derivation.\n"],
            },
            "acknowledgments in body text only": {
                "cell_type": "markdown",
                "source": ["See the ## Acknowledgments section below.\n"],
            },
        }

        for label, cell in accepted.items():
            with self.subTest(accepted=label):
                self.assertTrue(is_notebook_footer(cell))
        for label, cell in rejected.items():
            with self.subTest(rejected=label):
                self.assertFalse(is_notebook_footer(cell))

        # The real footers in the repository must still be recognised, so the
        # helper cannot be narrowed until it rejects them. Selected structurally
        # by heading and by in-page anchor link: selecting on the bare phrase
        # would re-admit the false positive above, and a correct lesson edit
        # that happens to mention it would then turn this test red.
        acknowledgments = backlinks = 0
        for path in notebook_paths():
            markdown = [
                cell
                for cell in notebook_cells(path)
                if cell.get("cell_type") == "markdown"
            ]
            for cell in markdown:
                if notebook_first_heading(cell) == "## Acknowledgments":
                    acknowledgments += 1
                    with self.subTest(notebook=path.name, footer="acknowledgments"):
                        self.assertTrue(is_notebook_footer(cell))
            if markdown and 'href="#top-' in "".join(markdown[-1].get("source", [])):
                backlinks += 1
                with self.subTest(notebook=path.name, footer="back to top"):
                    self.assertTrue(is_notebook_footer(markdown[-1]))

        self.assertTrue(acknowledgments)
        self.assertTrue(backlinks)

    def test_relative_links_point_at_files_that_exist(self) -> None:
        # The book build reports unreachable URLs as warnings so third-party
        # downtime cannot gate a merge. Internal link integrity is this
        # repository's own responsibility, so it is checked here instead, with
        # no network access and therefore no flakiness.
        relative_link = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
        skipped_schemes = ("http://", "https://", "mailto:", "data:", "attachment:", "#")
        offenders = []

        documents = [(path, path.parent, notebook_markdown(path)) for path in notebook_paths()]
        documents += [
            (REPO_ROOT / name, REPO_ROOT, (REPO_ROOT / name).read_text(encoding="utf-8"))
            for name in ("index.md", "local-setup.md", "README.md")
            if (REPO_ROOT / name).is_file()
        ]

        for source_path, base_dir, text in documents:
            for target in relative_link.findall(text):
                if target.startswith(skipped_schemes):
                    continue
                resolved = (base_dir / target.split("#", 1)[0]).resolve()
                if not resolved.exists():
                    offenders.append(f"{source_path.name} -> {target}")

        self.assertEqual([], offenders)

    def test_in_page_anchor_links_resolve_within_their_own_notebook(self) -> None:
        anchor_definition = re.compile(r'<div id="([^"]+)"></div>')
        in_page_link = re.compile(r'href="#([^"]+)"')
        all_identifiers: list[str] = []

        for path in notebook_paths():
            markdown = "\n".join(
                "".join(cell.get("source", []))
                for cell in notebook_cells(path)
                if cell.get("cell_type") == "markdown"
            )
            identifiers = anchor_definition.findall(markdown)
            targets = in_page_link.findall(markdown)
            all_identifiers.extend(identifiers)

            with self.subTest(notebook=path.name):
                # A link to #x must find its target in the same notebook, or the
                # rendered book resolves it against another notebook's page.
                self.assertEqual([], sorted(set(targets) - set(identifiers)))
                self.assertEqual(sorted(set(identifiers)), sorted(identifiers))

        # Identifiers are project-global in MyST, so a repeated one silently
        # retargets every in-page link that uses it to a different notebook.
        self.assertEqual(sorted(set(all_identifiers)), sorted(all_identifiers))


class NotebookPedagogyCellTests(unittest.TestCase):
    def test_installation_cells_are_hidden_in_the_book(self) -> None:
        installation_markers = (
            "!pip install",
            "!apt-get install",
            '"pip", "install"',
            "function load_qubonotebooks_bootstrap()",
            "Pkg.activate(",
            "Pkg.instantiate(",
        )

        for path in notebook_paths():
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                installation_cells = [
                    cell
                    for cell in notebook_cells(path)
                    if cell.get("cell_type") == "code"
                    and any(
                        marker in "".join(cell.get("source", []))
                        for marker in installation_markers
                    )
                ]

                self.assertTrue(installation_cells)
                for cell in installation_cells:
                    self.assertTrue(
                        {"hide-cell", "installation"}.issubset(
                            set(cell.get("metadata", {}).get("tags", []))
                        )
                    )

    def test_each_notebook_has_three_exercise_checkpoints(self) -> None:
        # Defect class: a notebook silently loses a workshop checkpoint or exposes
        # a solution because its required hide tags were removed.
        for path in notebook_paths():
            with self.subTest(notebook=path.relative_to(REPO_ROOT).as_posix()):
                cells = notebook_cells(path)
                exercise_cells = [
                    cell
                    for cell in cells
                    if cell.get("cell_type") == "code"
                    and "# EXERCISE" in "".join(cell.get("source", []))
                ]
                solution_cells = [
                    cell
                    for cell in cells
                    if cell.get("cell_type") == "code"
                    and "# SOLUTION (hidden in workshop version):"
                    in "".join(cell.get("source", []))
                ]

                self.assertGreaterEqual(len(exercise_cells), 3)
                self.assertGreaterEqual(len(solution_cells), 3)
                self.assertTrue(
                    all(
                        {"hide-cell", "solution"}.issubset(
                            set(cell.get("metadata", {}).get("tags", []))
                        )
                        for cell in solution_cells[:3]
                    )
                )
                self.assertTrue(
                    all(
                        any(
                            stripped
                            and not stripped.startswith("#")
                            for stripped in (
                                line.strip()
                                for line in "".join(cell.get("source", [])).splitlines()
                            )
                        )
                        for cell in solution_cells
                    )
                )
