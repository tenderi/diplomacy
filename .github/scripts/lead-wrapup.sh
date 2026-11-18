#!/usr/bin/env bash
# Runs after the lead agent, with no model calls, so it still works when the agent stopped
# because the Claude usage limit ran out -- the agent itself can't say anything then.
#
# Reads the stream-json transcript and the lead step's exit code (LEAD_RC; empty if the step
# never finished: cancelled or timed out), works out how the run ended, and on any abnormal
# end posts a salvage entry to the journal issue so the next run knows where to pick up.
# A usage-limit stop is a graceful end (warning, exit 0); a crash fails the job.
set -uo pipefail

transcript="${TRANSCRIPT:?}"
run_url="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"
last_result=""
[ -s "$transcript" ] && last_result=$(jq -rs '[.[] | select(.type == "result")] | last | .result // ""' "$transcript" 2>/dev/null)

if grep -qiE "hit your .*limit|usage limit|rate_limit" <<<"$last_result"; then
  outcome="usage limit"
  detail="$last_result"
elif [ "${LEAD_RC:-}" = "0" ]; then
  echo "Lead finished normally."
  exit 0
elif [ -z "${LEAD_RC:-}" ]; then
  outcome="cancelled or timed out"
  detail="The lead step didn't finish (job cancelled, or the 355-minute timeout)."
else
  outcome="crashed (exit ${LEAD_RC})"
  detail="${last_result:-no result event in the transcript}"
fi

# What the lead last said, and what it left in flight.
last_words=""
[ -s "$transcript" ] && last_words=$(jq -rs '[.[] | select(.type == "result" and (.is_error | not)) | .result] | last // ""' "$transcript" 2>/dev/null | head -c 2000)
# Subagent reports that never reached the journal. The transcript itself is not kept
# (no artifact: the repository is public and it holds production logs and query results),
# so their summaries go into the entry, capped.
subagent_reports=""
[ -s "$transcript" ] && subagent_reports=$(jq -r 'select(.type=="system" and .subtype=="task_notification")
    | "- **\(.status // "?")**: \(.summary // "" | gsub("\n"; " ") | .[0:600])"' "$transcript" 2>/dev/null | tail -n 12)
open_prs=$(gh pr list -R "$GITHUB_REPOSITORY" --json number,title,headRefName \
             -q '.[] | "- #\(.number) \(.title) (`\(.headRefName)`)"' 2>/dev/null)

body=$(cat <<MD
## Run $(date -u +%Y-%m-%d) — stopped: ${outcome}
**What happened:** ${detail}
**Lead's last report:**
${last_words:-_(none)_}

**Open PRs (finish, fix or close these first):**
${open_prs:-_(none)_}

**Subagent reports (latest 12):**
${subagent_reports:-_(none)_}

**Run:** ${run_url}

_Written by the workflow's wrap-up step, not by the agent._
<!-- lead-agent -->
MD
)

printf '%s\n' "$body" >> "$GITHUB_STEP_SUMMARY"
journal=$(gh issue list -R "$GITHUB_REPOSITORY" -l lead-journal --state open --json number -q '.[0].number' 2>/dev/null)
if [ -n "$journal" ]; then
  gh issue comment "$journal" -R "$GITHUB_REPOSITORY" --body "$body" >/dev/null && echo "Salvage entry posted to #$journal."
else
  echo "::warning::No open lead-journal issue (are issues enabled?); salvage entry is only in the step summary."
fi

if [ "$outcome" = "usage limit" ]; then
  echo "::warning::Lead stopped at the Claude usage limit: $detail"
  exit 0
fi
echo "::error::Lead ${outcome}."
exit 1
