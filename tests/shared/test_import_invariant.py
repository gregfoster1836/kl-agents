"""Enforce the one hard kl-agent contract invariant: shared/ never imports agents/.

This is an AST check, not a grep (Codex round-1 finding #3): it parses every
shared/**/*.py file and inspects real import statements, so it ignores the word
"agents" in comments, docstrings, and string literals that a text search would
false-positive on. A violating import fails this test, which is how the spine
stays independent of any single agent.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SHARED_ROOT = Path(__file__).resolve().parent.parent.parent / "shared"


def _shared_py_files() -> list[Path]:
    return sorted(_SHARED_ROOT.rglob("*.py"))


def _imports_root_is_agents(node: ast.AST) -> bool:
    """True if an Import/ImportFrom node's root module is the `agents` package."""
    if isinstance(node, ast.Import):
        return any(alias.name == "agents" or alias.name.startswith("agents.") for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        # node.module is None for `from . import x`; a relative import inside
        # shared/ can never reach agents/, so it is safe.
        mod = node.module or ""
        return mod == "agents" or mod.startswith("agents.")
    return False


def test_shared_root_exists() -> None:
    assert _SHARED_ROOT.is_dir(), f"shared/ not found at {_SHARED_ROOT}"
    assert _shared_py_files(), "no python files found under shared/"


@pytest.mark.parametrize("path", _shared_py_files(), ids=lambda p: str(p.name))
def test_shared_file_does_not_import_agents(path: Path) -> None:
    """No file under shared/ may import from the agents package."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders = [
        ast.dump(node)
        for node in ast.walk(tree)
        if _imports_root_is_agents(node)
    ]
    assert not offenders, (
        f"{path} imports from agents/ (violates the shared->agents invariant): {offenders}"
    )
