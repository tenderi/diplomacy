#!/usr/bin/env bash
# PostToolUse hook for the lead agent (and its subagents, which run in the same process):
# once the Claude usage limit is nearly spent, tell the agent to stop and write the journal
# while it still has tokens to do so. Without this the run goes on until the limit cuts it off
# mid-sentence, and only the workflow's salvage entry gets written.
#
# The usage comes from the run's own stream-json transcript (LEAD_TRANSCRIPT): Claude Code
# emits a rate_limit_event line whenever a window's rounded utilization moves, read from the
# response headers of every main-loop and subagent call. Every window counts (5-hour,
# 7-day, ...): whichever runs out first stops the run. LEAD_USAGE_STOP is the threshold as
# a fraction used (default 0.90, i.e. 10% left).
#
# Prints nothing below the threshold. Never fails the tool call: any problem is a silent
# exit 0, since a broken guard must not stop the agent working.
set -uo pipefail
cat >/dev/null   # the hook input on stdin; not needed

transcript=${LEAD_TRANSCRIPT:-}
limit=${LEAD_USAGE_STOP:-0.90}
[ -s "$transcript" ] || exit 0
# grep narrows the (large) transcript cheaply; jq then keeps only real events, not text that
# merely quotes the name.
line=$(grep -F '"rate_limit_event"' "$transcript" \
         | jq -cR 'fromjson? | select(.type? == "rate_limit_event")' 2>/dev/null | tail -1)
[ -n "$line" ] || exit 0

read -r used window resets < <(jq -r '.rate_limit_info
  | [ (.unifiedWindows // {} | to_entries[] | {w: .key, u: .value.utilization, r: .value.resetsAt}),
      {w: (.rateLimitType // "current"), u: (if .status == "rejected" then 1 else .utilization end), r: .resetsAt} ]
  | map(select(.u != null)) | max_by(.u) // empty
  | "\(.u) \(.w) \(.r // 0)"' <<<"$line" 2>/dev/null) || exit 0
[ -n "${used:-}" ] || exit 0
awk -v u="$used" -v l="$limit" 'BEGIN { exit !(u >= l) }' || exit 0

pct=$(awk -v u="$used" 'BEGIN { printf "%d", u * 100 }')
when=unknown; [ "${resets:-0}" -gt 0 ] 2>/dev/null && when=$(date -u -d "@$resets" +"%Y-%m-%d %H:%M UTC")
msg="USAGE LIMIT NEARLY SPENT: the ${window} Claude usage window is at ${pct}% (resets ${when}); the run stops at $(awk -v l="$limit" 'BEGIN { printf "%d", l * 100 }')%. Stop starting new work now. If you are a subagent: commit and push what you have to your branch, then report back at once with the state of the work. If you are the lead: spawn nothing more, merge nothing more, and finish the journal entry now (what shipped, what is in flight, open PRs, what the next run should do first), then end the run. This message repeats after every tool call."
jq -n --arg m "$msg" '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: $m}}'
