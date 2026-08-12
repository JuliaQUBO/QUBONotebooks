#!/usr/bin/env python3
"""Check committed notebook output against the budgets in CONTRIBUTING.md.

The budgets and the documented exceptions are read from CONTRIBUTING.md rather
than restated here, so the policy a contributor reads is the policy this check
enforces.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = REPO_ROOT / "CONTRIBUTING.md"
NOTEBOOK_DIRS = ("notebooks_jl", "notebooks_py")
BUDGET_HEADING = "### Size budgets"
EXCEPTION_HEADING = "### Documented exceptions"
CELL_SCOPE = "One code cell"
NOTEBOOK_SCOPE = "One notebook"
COLLECTION_SCOPE = "All notebooks"
GRANTABLE_SCOPES = (CELL_SCOPE, NOTEBOOK_SCOPE)
KILOBYTE = 1024
SIZE_UNITS = {"KB": KILOBYTE, "MB": KILOBYTE * KILOBYTE}
SIZE_PATTERN = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(KB|MB)")


def parse_size(text: str) -> int:
    """Return the byte count of a policy size such as ``256 KB`` or ``1.0 MB``."""
    match = SIZE_PATTERN.match(text.strip())
    if match is None:
        raise ValueError(f"Not a policy size: {text!r}. Use a value such as '256 KB'.")
    return round(float(match.group(1)) * SIZE_UNITS[match.group(2)])


def format_size(size_bytes: int) -> str:
    if size_bytes >= SIZE_UNITS["MB"]:
        return f"{size_bytes / SIZE_UNITS['MB']:.2f} MB"
    return f"{size_bytes / KILOBYTE:.1f} KB"


def markdown_table_rows(
    document: str,
    heading: str,
    required_columns: tuple[str, ...],
    allow_no_rows: bool = False,
) -> list[dict[str, str]]:
    """Return the rows of the first Markdown table under ``heading``.

    The policy lives in prose, so every way of breaking the table has to report
    what to fix rather than raise from wherever a value was later read.

    ``allow_no_rows`` covers a table whose empty state is meaningful: the
    exceptions table is expected to lose its last row once reductions land, so
    requiring one would force a dummy grant to stay behind.
    """
    lines = document.splitlines()
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise ValueError(f"{POLICY_PATH.name} has no {heading!r} section.") from exc

    table = []
    for line in lines[start + 1 :]:
        stripped = line.strip()
        if stripped.startswith("|"):
            table.append([cell.strip().strip("`") for cell in stripped.strip("|").split("|")])
        elif table:
            break
        elif stripped.startswith("#"):
            raise ValueError(f"{POLICY_PATH.name} has no table under {heading!r}.")

    if len(table) < 2:
        raise ValueError(f"{POLICY_PATH.name} has no table under {heading!r}.")

    header, _separator, *body = table
    if not body and not allow_no_rows:
        raise ValueError(f"The table under {heading!r} has no rows.")

    missing = [column for column in required_columns if column not in header]
    if missing:
        raise ValueError(
            f"The table under {heading!r} is missing the column(s) {missing} that "
            f"the check reads. Its columns are {header}."
        )

    rows = []
    for row in body:
        if len(row) != len(header):
            raise ValueError(
                f"A row under {heading!r} has {len(row)} cells for {len(header)} "
                f"columns: {row}."
            )
        rows.append(dict(zip(header, row)))
    return rows


@dataclass(frozen=True)
class Policy:
    """Budgets by scope name, and the granted ceilings that override them."""

    budgets: dict[str, int]
    grants: dict[tuple[str, str], int]

    def ceiling(self, notebook: str, scope: str) -> int:
        return self.grants.get((notebook, scope), self.budgets[scope])

    def is_granted(self, notebook: str, scope: str) -> bool:
        return (notebook, scope) in self.grants


def load_policy(document: str) -> Policy:
    budgets = {
        row["Scope"]: parse_size(row["Budget"])
        for row in markdown_table_rows(document, BUDGET_HEADING, ("Scope", "Budget"))
    }
    missing = {CELL_SCOPE, NOTEBOOK_SCOPE, COLLECTION_SCOPE} - set(budgets)
    if missing:
        raise ValueError(f"The size-budget table is missing scopes: {sorted(missing)}.")

    grants: dict[tuple[str, str], int] = {}
    exception_rows = markdown_table_rows(
        document,
        EXCEPTION_HEADING,
        ("Notebook", "Scope", "Granted ceiling"),
        allow_no_rows=True,
    )
    for row in exception_rows:
        scope = row["Scope"]
        if scope not in GRANTABLE_SCOPES:
            raise ValueError(
                f"Exception scope {scope!r} is not one of {list(GRANTABLE_SCOPES)}. "
                f"The {COLLECTION_SCOPE!r} budget takes no exception."
            )
        key = (row["Notebook"], scope)
        if key in grants:
            raise ValueError(f"Duplicate exception row for {key[0]} at scope {scope!r}.")
        grants[key] = parse_size(row["Granted ceiling"])

    return Policy(budgets=budgets, grants=grants)


def cell_output_bytes(cell: dict) -> int:
    """Return the size of one cell's stored output as the policy measures it.

    Compact separators are part of the definition in CONTRIBUTING.md: the
    default `", "` and `": "` add a byte per delimiter, which measures output the
    policy does not describe.
    """
    return len(
        json.dumps(
            cell.get("outputs", []), ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    )


@dataclass(frozen=True)
class Measurement:
    notebook: str
    stored_bytes: int
    cell_bytes: tuple[tuple[int, int], ...]

    @property
    def largest_cell(self) -> tuple[int, int]:
        if not self.cell_bytes:
            return (-1, 0)
        return max(self.cell_bytes, key=lambda item: item[1])


def measure_notebook(path: Path, name: str) -> Measurement:
    """Measure ``path``, recorded under ``name``.

    The name is required because the exceptions are keyed by repository-relative
    path: a measurement recorded under a bare filename matches no grant, and the
    mismatch would surface as a complaint about the policy table.
    """
    notebook = json.loads(path.read_text())
    cell_bytes = tuple(
        (index, cell_output_bytes(cell))
        for index, cell in enumerate(notebook["cells"])
        if cell.get("cell_type") == "code"
    )
    return Measurement(
        notebook=name,
        stored_bytes=sum(size for _index, size in cell_bytes),
        cell_bytes=cell_bytes,
    )


def measure_repository(repo_root: Path = REPO_ROOT) -> list[Measurement]:
    measurements = [
        measure_notebook(path, path.relative_to(repo_root).as_posix())
        for directory in NOTEBOOK_DIRS
        for path in sorted((repo_root / directory).glob("*.ipynb"))
    ]
    if not measurements:
        raise ValueError(
            f"Found no notebooks in {list(NOTEBOOK_DIRS)} under {repo_root}. The "
            "budgets cover every published notebook, so an empty set is a "
            "discovery failure rather than a clean result."
        )
    return measurements


def check(policy: Policy, measurements: list[Measurement]) -> list[str]:
    """Return one message per budget violation, empty when the tree conforms."""
    measured = {measurement.notebook: measurement for measurement in measurements}
    violations = []

    for notebook, scope in sorted(policy.grants):
        ceiling = policy.grants[(notebook, scope)]
        budget = policy.budgets[scope]
        if notebook not in measured:
            violations.append(
                f"{notebook}: documented exception for {scope!r} names a notebook "
                f"that does not exist."
            )
            continue
        if ceiling <= budget:
            violations.append(
                f"{notebook}: the {scope!r} exception grants {format_size(ceiling)}, "
                f"which the {format_size(budget)} budget already allows. Remove the row."
            )
            continue
        actual = (
            measured[notebook].stored_bytes
            if scope == NOTEBOOK_SCOPE
            else measured[notebook].largest_cell[1]
        )
        if actual <= budget:
            violations.append(
                f"{notebook}: the {scope!r} exception is no longer needed — "
                f"{format_size(actual)} now fits the {format_size(budget)} budget. "
                f"Remove the row."
            )

    for measurement in measurements:
        notebook = measurement.notebook
        notebook_ceiling = policy.ceiling(notebook, NOTEBOOK_SCOPE)
        if measurement.stored_bytes > notebook_ceiling:
            violations.append(
                f"{notebook}: stores {format_size(measurement.stored_bytes)} of output, "
                f"over the {format_size(notebook_ceiling)} "
                f"{'granted ceiling' if policy.is_granted(notebook, NOTEBOOK_SCOPE) else 'budget'}."
            )

        cell_ceiling = policy.ceiling(notebook, CELL_SCOPE)
        for index, size in measurement.cell_bytes:
            if size > cell_ceiling:
                violations.append(
                    f"{notebook}: cell {index} stores {format_size(size)} of output, "
                    f"over the {format_size(cell_ceiling)} "
                    f"{'granted ceiling' if policy.is_granted(notebook, CELL_SCOPE) else 'budget'}."
                )

    stored_total = sum(measurement.stored_bytes for measurement in measurements)
    collection_budget = policy.budgets[COLLECTION_SCOPE]
    if stored_total > collection_budget:
        violations.append(
            f"All notebooks: store {format_size(stored_total)} of output, over the "
            f"{format_size(collection_budget)} budget. This budget takes no exception."
        )

    return violations


def report(policy: Policy, measurements: list[Measurement]) -> str:
    lines = [
        f"{'notebook':44s} {'stored':>10s} {'ceiling':>10s} "
        f"{'largest cell':>13s} {'ceiling':>10s}",
    ]
    for measurement in sorted(measurements, key=lambda item: -item.stored_bytes):
        notebook = measurement.notebook
        index, size = measurement.largest_cell
        lines.append(
            f"{notebook:44s} {format_size(measurement.stored_bytes):>10s} "
            f"{format_size(policy.ceiling(notebook, NOTEBOOK_SCOPE)):>10s} "
            f"{f'#{index}: ' + format_size(size):>13s} "
            f"{format_size(policy.ceiling(notebook, CELL_SCOPE)):>10s}"
        )

    stored_total = sum(measurement.stored_bytes for measurement in measurements)
    lines.append(
        f"\n{len(measurements)} notebooks store {format_size(stored_total)} of output, "
        f"against a {format_size(policy.budgets[COLLECTION_SCOPE])} budget."
    )
    return "\n".join(lines)


def main() -> int:
    policy = load_policy(POLICY_PATH.read_text())
    measurements = measure_repository()
    print(report(policy, measurements))

    violations = check(policy, measurements)
    if not violations:
        print("\nEvery notebook is within its documented output budget.")
        return 0

    print(f"\n{len(violations)} output-budget violation(s):")
    for violation in violations:
        print(f"  - {violation}")
    print(
        "\nReduce the stored output, or record a reviewed exception in the "
        f"'{EXCEPTION_HEADING.lstrip('# ')}' table of {POLICY_PATH.name}."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
