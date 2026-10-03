#!/usr/bin/env bash
# Which Test Suite jobs does this change need? Reads changed paths (one per line) on stdin and
# prints two lines in $GITHUB_OUTPUT format:
#
#   code=true|false  false only when every path is documentation: a Markdown file anywhere, or
#                    anything under docs/. Exception: docs/TELEGRAM_BOT_COMMANDS.md, whose
#                    order-syntax block tests/test_bot_help_text.py parses. Keep this narrow: a
#                    path wrongly called docs-only merges untested.
#   docs=true|false  true when any input of the docs site changed (docs/, mkdocs.yml,
#                    docker/docs.Dockerfile), so the strict MkDocs build runs before merge
#                    instead of failing the deploy after it.
#
# An empty list (unknown diff) sets both to true, so when in doubt, everything runs.
set -euo pipefail

code=false
docs=false
seen=0
while IFS= read -r path; do
  [ -n "$path" ] || continue
  seen=1
  case "$path" in
    docs/* | mkdocs.yml | docker/docs.Dockerfile) docs=true ;;
  esac
  case "$path" in
    docs/TELEGRAM_BOT_COMMANDS.md) code=true ;;
    *.md | docs/*) ;;
    *) code=true ;;
  esac
done
if [ "$seen" = 0 ]; then
  code=true
  docs=true
fi
echo "code=$code"
echo "docs=$docs"
