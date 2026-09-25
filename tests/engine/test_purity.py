"""The engine is pure rules logic: it imports the standard library and itself, nothing else.

No database, web framework, renderer or HTTP client may creep in; persistence, rendering and
the servers are adapters *around* ``GameService``. Checked on every import statement of every
engine module, not by grepping for a few package names.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ENGINE = Path(__file__).parent.parent.parent / "src" / "engine"


def test_engine_imports_only_the_standard_library_and_itself() -> None:
    allowed = set(sys.stdlib_module_names) | {"engine"}
    offenders = []
    for path in sorted(ENGINE.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots = [node.module.split(".")[0]]
            else:
                continue
            offenders += [f"{path.relative_to(ENGINE)}: {root}" for root in roots if root not in allowed]
    assert not offenders, "\n".join(offenders)
