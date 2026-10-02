#!/usr/bin/env bash
# Preflight for the lead agent: is there Claude usage left? There's no API that reports the
# remaining subscription quota, so this asks the model for one word with the run's own model.
# The weekly limit can be per model, so a cheaper model could pass while the real one is out.
# When the limit is exhausted, the call fails at once with the same "You've hit your ... limit"
# result the lead would hit, and the run is skipped before any setup is spent.
#
# Writes available=true|false to $GITHUB_OUTPUT. Out of usage is a graceful skip (exit 0, and a
# note on the triggering issue, so the maintainer knows when it'll be picked up); any other
# failure (bad token, CLI error) fails the job, because that needs fixing.
set -uo pipefail

# A one-line system prompt and no tools keep it to ~500 input tokens (~$0.002, against ~$0.23
# with Claude Code's default context). stderr is kept apart: a warning line mixed into stdout
# would make the JSON unparseable and turn a healthy probe into a failure.
errfile=$(mktemp)
out=$(claude -p "Reply with the single word OK." --model "${MODEL:?}" --max-turns 1 \
        --system-prompt "You are a health check." --tools "" \
        --output-format json 2>"$errfile")
rc=$?
err=$(cat "$errfile"); rm -f "$errfile"
result=$(jq -r '.result // empty' <<<"$out" 2>/dev/null || true)
is_error=$(jq -r '.is_error | tostring' <<<"$out" 2>/dev/null || true)  # not `//`: it treats false as missing

if [ "$rc" = "0" ] && [ "$is_error" = "false" ]; then
  echo "Usage available (probe answered: ${result:0:40})."
  echo "available=true" >> "$GITHUB_OUTPUT"
  exit 0
fi

if grep -qiE "hit your .*limit|usage limit|rate_limit" <<<"$result $out $err"; then
  reason=${result:-$(grep -oiE "you've hit your[^\"]*" <<<"$out $err" | head -1)}
  echo "available=false" >> "$GITHUB_OUTPUT"
  echo "::warning::Skipping the lead run: out of Claude usage ($reason)."
  printf '## Lead run skipped: out of Claude usage\n%s\n' "$reason" >> "$GITHUB_STEP_SUMMARY"
  if [ -n "${ISSUE_NUMBER:-}" ]; then
    gh issue comment "$ISSUE_NUMBER" -R "$GITHUB_REPOSITORY" --body "$(printf \
      'The lead agent is out of Claude usage right now (%s), so this run was skipped. It will pick this issue up on the next run: the nightly one at 00:00 UTC, or any later trigger.\n\n<!-- lead-agent -->' \
      "$reason")" >/dev/null || echo "::warning::Couldn't comment on #$ISSUE_NUMBER."
  fi
  exit 0
fi

echo "::error::Usage probe failed (exit $rc): ${out:0:300} ${err:0:300}"
exit 1
