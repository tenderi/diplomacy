"""The bot as production runs it: ``python -m server.telegram_bot`` in an image that holds
only ``src/server/telegram_bot`` and ``requirements-bot.txt`` (``docker/bot.Dockerfile``).

A test run imports the bot with the whole of ``src`` and every API dependency on the path,
so nothing else would notice a bot module reaching for the engine, SQLAlchemy or a sibling
``server`` module -- the image would crash on start while the suite stayed green.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).parent.parent / "src"
BOT = SRC / "server" / "telegram_bot"
# What requirements-bot.txt installs (python-telegram-bot is imported as ``telegram``).
BOT_THIRD_PARTY = {"telegram", "requests"}

pytestmark = pytest.mark.execution_context


def _imported_roots(path: Path) -> set[str]:
    """Top-level names a module imports, with ``server.telegram_bot.x`` kept whole."""
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            roots.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module)
    return roots


def test_bot_imports_only_what_its_image_contains() -> None:
    allowed_roots = set(sys.stdlib_module_names) | BOT_THIRD_PARTY
    offenders = []
    for path in sorted(BOT.rglob("*.py")):
        for name in _imported_roots(path):
            if name.startswith("server."):
                if not name.startswith("server.telegram_bot"):
                    offenders.append(f"{path.relative_to(SRC)}: {name}")
            elif name.split(".")[0] not in allowed_roots:
                offenders.append(f"{path.relative_to(SRC)}: {name}")
    assert not offenders, "the bot image does not contain these:\n" + "\n".join(offenders)


def test_no_module_shadows_the_package() -> None:
    """``server/telegram_bot.py`` next to the package once made ``python -m server.telegram_bot``
    fail in production: the package wins the import and the module is dead."""
    assert not (SRC / "server" / "telegram_bot.py").exists()


def test_python_dash_m_starts_and_stops_on_the_missing_token() -> None:
    """The image's CMD, run with only ``src`` on the path: it must get as far as asking for
    ``TELEGRAM_BOT_TOKEN`` -- i.e. every module imported and ``__main__`` ran."""
    env = {k: v for k, v in os.environ.items() if k != "TELEGRAM_BOT_TOKEN"}
    env["PYTHONPATH"] = str(SRC)
    result = subprocess.run(
        [sys.executable, "-m", "server.telegram_bot"],
        cwd=str(SRC.parent),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 1, "a misconfigured bot must not report a clean exit"
    assert "TELEGRAM_BOT_TOKEN environment variable not set" in result.stderr, result.stderr[-2000:]
