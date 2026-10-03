"""`.github/scripts/ci-changes.sh`: which changes skip the Test Suite.

A path wrongly classed as docs-only merges with no tests run, so these pin the
classification in both directions, and the workflow wiring that makes a skip
satisfy branch protection rather than block it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPT = REPO_ROOT / ".github" / "scripts" / "ci-changes.sh"
TEST_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"


def _classify(*paths: str) -> str:
    result = subprocess.run(
        ["bash", str(SCRIPT)], input="\n".join(paths) + "\n", capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    "paths",
    [
        ("README.md",),
        ("CLAUDE.md", ".claude/lead/CHARTER.md", ".claude/agents/worker.md"),
        ("docs/specs/fix_plan.md", "docs/DEPLOYMENT.md"),
        ("docs/reference/rules.pdf",),
    ],
)
def test_documentation_only_skips(paths: tuple[str, ...]) -> None:
    assert _classify(*paths) == "code=false"


@pytest.mark.infrastructure
@pytest.mark.parametrize(
    "paths",
    [
        ("src/engine/game.py",),
        ("docs/specs/fix_plan.md", "src/server/legal_orders.py"),  # one code file is enough
        ("frontend/package.json",),
        (".github/workflows/test.yml",),
        ("mkdocs.yml",),  # configures the docs site, but isn't under docs/
        ("requirements.txt",),
        # tests/test_bot_help_text.py parses this file's order-syntax block.
        ("docs/TELEGRAM_BOT_COMMANDS.md",),
        ("docs/index.md", "docs/TELEGRAM_BOT_COMMANDS.md"),
    ],
)
def test_anything_else_runs_everything(paths: tuple[str, ...]) -> None:
    assert _classify(*paths) == "code=true"


@pytest.mark.infrastructure
def test_an_unknown_diff_runs_everything() -> None:
    """A new branch's all-zero `before` makes `git diff` fail, leaving an empty list."""
    assert _classify() == "code=true"


@pytest.mark.infrastructure
def test_the_required_checks_skip_by_job_if_not_by_paths_ignore() -> None:
    """A job skipped by its `if:` reports success to branch protection; a workflow that
    never starts (paths-ignore) leaves `test`/`frontend`/`security` pending forever."""
    workflow = TEST_WORKFLOW.read_text()
    triggers = workflow.split("\non:\n", 1)[1].split("\n\n", 1)[0]
    assert "pull_request:" in triggers
    assert "paths" not in triggers, triggers
    for job in ("test", "frontend", "security"):
        block = re.search(rf"\n  {job}:\n(.*?)(?=\n  \w[\w-]*:\n|\Z)", workflow, re.S)
        assert block is not None, f"job {job} is missing"
        assert "    needs: changes\n    if: needs.changes.outputs.code == 'true'\n" in block.group(1), job
