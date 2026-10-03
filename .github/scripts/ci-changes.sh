#!/usr/bin/env bash
# Does this change need the full Test Suite? Reads changed paths (one per line) on stdin and
# prints `code=true` or `code=false`, in $GITHUB_OUTPUT format.
#
# false only when every path is documentation: a Markdown file anywhere, or anything under
# docs/. Exception: docs/TELEGRAM_BOT_COMMANDS.md, whose order-syntax block
# tests/test_bot_help_text.py parses. An empty list (unknown diff) counts as code, so when in
# doubt, everything runs. Keep this list narrow: a path wrongly called docs-only merges untested.
set -euo pipefail

code=false
seen=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  seen=1
  case "$path" in
    docs/TELEGRAM_BOT_COMMANDS.md) code=true ;;
    *.md | docs/*) ;;
    *) code=true ;;
  esac
done
[ "$seen" = 1 ] || code=true
echo "code=$code"
