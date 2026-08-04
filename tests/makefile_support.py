"""Helpers for testing evaluated Make behavior instead of Makefile source."""

from __future__ import annotations

import shlex


def command_with_assignment(output: str, name: str) -> list[str]:
    """Return the evaluated Make command carrying a named assignment."""
    prefix = f"{name}="
    for line in output.splitlines():
        command = shlex.split(line)
        if any(token.startswith(prefix) for token in command):
            return command
    raise AssertionError(f"No Make command assigned {name}")
