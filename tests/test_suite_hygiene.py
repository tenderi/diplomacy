"""The suite checks itself: a test must be able to fail.

Placeholder tests whose body was ``pass`` inside ``try/except``, and ``hasattr``
checks standing in for behaviour, sat in this suite for months, green whatever the
code did. This guard fails on any test function with no assertion of any kind.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).parent

# Calls that assert: pytest.raises/fail, mock assert_* methods, and helpers whose
# names say they assert (h.assert_success, self._check, _assert_rendered, ...).
_ASSERTING_CALL = ("assert", "raises", "fail", "check", "expect")


def _asserts(fn: ast.AST) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if any(word in name.lower() for word in _ASSERTING_CALL):
                return True
        if isinstance(node, ast.With) and any(
            isinstance(item.context_expr, ast.Call) and "raises" in ast.unparse(item.context_expr.func)
            for item in node.items
        ):
            return True
    return False


def test_every_test_can_fail() -> None:
    offenders = []
    for path in sorted(TESTS.rglob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                if not _asserts(node):
                    offenders.append(f"{path.relative_to(TESTS)}:{node.lineno} {node.name}")
    assert not offenders, "tests with nothing that can fail:\n" + "\n".join(offenders)
