"""TEMPORARY probe -- proves the CI `security` job fails on a real bandit finding.

This file exists only to demonstrate C1's acceptance criterion and must never
be merged. See docs/specs/fix_plan.md, Track C, C1.
"""
import subprocess


def run_user_command(user_input: str) -> int:
    """Deliberate B602: shell=True on caller-supplied input."""
    return subprocess.call(user_input, shell=True)
