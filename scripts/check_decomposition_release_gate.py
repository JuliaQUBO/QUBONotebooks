#!/usr/bin/env python3
"""Refuse stale/source-pinned locks for the pending notebook-12 rewrite."""
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "notebooks_jl/environments/12-Decomposition"


def readiness_errors(project=PROJECT):
    gate = tomllib.loads((project / "RELEASE-GATES.toml").read_text())
    errors = []
    if gate.get("status") != "ready":
        errors.append(gate["reason"])
    accepted = gate.get("decomposition_version", "")
    if not accepted or not gate.get("published_release_evidence"):
        errors.append("Accepted published decomposition release/evidence is not recorded")
    spec = tomllib.loads((project / "Project.toml").read_text())
    if spec.get("sources"):
        errors.append("Project still declares source overrides")
    for filename in ("Manifest.toml", "Manifest-v1.12.toml"):
        lock = tomllib.loads((project / filename).read_text())
        for name in ("QUBODrivers", "QUBODecomposition", "HiGHS"):
            entries = lock["deps"].get(name, [])
            if len(entries) != 1:
                errors.append(f"{filename}: missing registered {name}")
                continue
            entry = entries[0]
            if any(k in entry for k in ("path", "repo-url", "repo-rev")):
                errors.append(f"{filename}: {name} is source/path tracked")
            if name == "QUBODrivers" and tuple(map(int, entry["version"].split(".")[:3])) < (0, 6, 6):
                errors.append(f"{filename}: corrected driver >=0.6.6 is required")
            if name == "QUBODecomposition" and entry["version"] != accepted:
                errors.append(f"{filename}: accepted standalone decomposition release is required")
    return errors


if __name__ == "__main__":
    errors = readiness_errors()
    if errors:
        print("Notebook 12 release/install validation is pending:\n- " + "\n- ".join(errors), file=sys.stderr)
        sys.exit(2)
    print("Notebook 12 published dependency locks are ready")
