# Fix Plan — Living Tracker: Open Work Only

> **This file is the single source of truth for what to work on next.** Any agent or model
> picking up this project: read this file top to bottom, then continue at the first unchecked
> task of the highest-priority track.
>
> **Completed work is not here.** Tracks A–E (the port, the post-rewrite cleanup, security
> hardening, full DAIDE support, and client UX) are all merged and archived in
> [`done_fixes.md`](done_fixes.md), together with their findings, rejected alternatives, and
> verification evidence. Read that file when you need the *why* behind existing code; read
> this one to decide what to do.
>
> **Maintenance contract (non-negotiable):**
> - Check off tasks (`[x]`) in the same commit as the work that completes them.
> - Keep the **Status** block below current: track, next action, date.
> - Newly discovered work becomes a new unchecked task under the right track — never done
>   silently.
> - If a design decision here is changed, edit this file to say what changed and why.
> - **When a track completes, move its whole section to `done_fixes.md` verbatim** — findings
>   and evidence included — and delete it from this file. This file only ever grows sideways,
>   never downward.

## Status

- **Last updated:** 2026-09-24, at `v2.7.97`. `main` green.
- **Y2 — deadline-proposal hardening, landed `v2.7.97`** (bug hunt over Track Y's new code,
  probed against the local Postgres): unchecked `hours`/`vote_hours` (a negative `hours`
  that won its vote set a deadline in the past; `NaN`/`Infinity`/`1e12` were 500s, the last
  one only on the deciding vote, *after* the proposal was deleted), an accepted proposal
  never re-armed the 10-minute reminder, and a finished game still took deadline writes.
  See Y2 below.
- **Track Y — majority-vote deadline proposals, landed `v2.7.96`.** The maintainer,
  after reviewing Track X's channel proposal-voting stub, decided that feature wasn't
  worth finishing (it was never reachable from any real bot command anyway) and asked
  for the effort redirected: `/deadline` can still be set unilaterally by any single
  player exactly as before, but now also supports `propose`/`vote`/`withdraw` for a
  table that would rather change the pace by majority agreement. See the Track Y
  section below for the full design (majority not unanimity, one proposal pending at a
  time, an optional per-proposal vote expiry).
- **Track X — Telegram bot command audit, prompted by a maintainer report that
  Help -> Run Perfect Demo Game failed — complete**, `v2.7.92`–`v2.7.94`. See the
  Track X section below for the full writeup — the short version: two menu items were
  calling code that could never have worked (removed), and the entire channel-integration
  feature (`/link_channel`'s promised auto-posted maps/broadcasts/notifications, plus six
  more manually-triggered channel posts) turned out to have been silently non-functional
  since it was written, for a third, independent reason each time (wrong process, wrong
  async convention, or both) — now fixed and verified against a live server, not just unit
  tests. Proposal-vote *tallying* (a documented stub before this track, not a
  wrong-process bug) was later removed outright rather than finished — see Track Y0.
- **Track W — recovered uncommitted work from `origin/vps-split` (`v2.7.90`) plus W0
  (`v2.7.91`).** `cfa8d93` (the audit referenced below) was never merged, but real code
  implementing four of its findings was sitting **uncommitted** on `vps-split` and was
  recovered, ported onto current `main`, and adapted where the two had diverged (see W1
  below): W2 (per-game `phase_length_seconds`, explicit-arm only), W3 (DATC 6.A naming
  gaps, 6.K.1/6.K.2, a full-game-replay regression fixture), W4 (`resolution_history`,
  `messages.phase_code`, a working `/history/{turn}` — found and fixed a *second*,
  unrelated bug: it read columns that don't exist on `MapSnapshotModel` and had 500'd for
  its entire existence), and W5 (admin-only `GET /games/{id}/export` / `POST
  /games/import`). **W0 landed as `v2.7.91`**: `old_implementation/` is deleted (the audit's
  own verdict was "safe to delete"), `rules.pdf` relocated to `docs/reference/`, every
  pointer updated, full suite green afterwards. Only W6 and W7 remain, both
  maintainer-decision tables. Uses "W" rather than the recovered commit's own "K"
  numbering because this file's Track K (phase-aware order acceptance, `v2.7.69`) already
  used that letter for something unrelated.
- **Track V — the whole stack on one VPS, landed as `v2.7.85`** and is archived in
  [`done_fixes.md`](done_fixes.md). The maintainer chose to retire the VPS + home-server
  split: `docker-compose.yml` now runs `postgres`, `diplomacy_api`, `diplomacy_bot` and
  `diplomacy_web` on the VPS, only nginx public. Every secret but the Telegram token is
  generated on the host (`ensure_env.sh`); `deploy.yml` (renamed from `deploy-control.yml`)
  deploys everything on each green merge and fails if the API or the site does not answer.
  The home database held **no games** (`GET /games` → `[]`, checked over the tunnel before
  the switch), so nothing was migrated. Remaining host chores are F3 below.
- **VPS facts (2026-09-23):** login is **`root`** only (keys only); checkout at
  `/root/diplomacy`, a **single-branch** clone of `vps-split` (the workflow fetches its target
  by SHA, so that no longer matters); 1 vCPU, 1.8 GB RAM, **2 GB swap added** for Track V;
  p2p's `p2p-downloader_bot` shares the host. Deploy-on-merge has been live since `v2.7.84`
  (the `v2.7.82`–`v2.7.84` fixes that got it there are under Track U in `done_fixes.md`).
  `cfa8d93` (a docs-only "Track K — audit of old_implementation") itself was never merged;
  the code it inspired was recovered separately as Track W above.
- **Track U — deploy-on-merge for the VPS, AWS removed, landed as `v2.7.80`** and is archived
  in [`done_fixes.md`](done_fixes.md). The Terraform/EC2/OIDC layout and its workflow are
  gone; the workflow itself was reshaped for one host in Track V. `config.py` no longer logs the token.
- **Track T — auth sweep, landed as `v2.7.79`** and is archived in
  [`done_fixes.md`](done_fixes.md). `GET /users/{id}/games` was anonymous (and cached, so the
  fix had to be a dependency); `POST /deadline` let any Bearer user set any game's deadline;
  two dead anonymous session routes were an unbounded memory sink.
- **Track S — waiting-list writes accepted any browser account, landed as `v2.7.78`** and is
  archived in [`done_fixes.md`](done_fixes.md). Any Bearer token could enqueue or dequeue an
  arbitrary telegram id; the routes now require the bot secret, as their docstring intended.
- **Track R — `POST /restore` took no credentials, landed as `v2.7.77`** and is archived in
  [`done_fixes.md`](done_fixes.md). Anyone on the internet could rewind any game; now admin
  token only, and the players are told. Snapshot and generate_map routes need a caller.
- **Track Q — routes that 500'd their own 404s, messaging edge cases, landed as `v2.7.76`**
  and is archived in [`done_fixes.md`](done_fixes.md). Fifteen API tests accepted a 500 and so
  hid two routes that wrapped their own 404s; seven such `try` blocks fixed. Power names are
  now case-insensitive on every seat lookup; a private message to a vacated seat is refused.
- **Track P — `/quit` never vacated the seat landed as `v2.7.75`** and is archived in
  [`done_fixes.md`](done_fixes.md). Both `/quit` and `/replace` wrote `user_id` on a detached
  ORM row (the pattern the deadline docstring warns about), so a quitter kept full control of
  the power and a seat could never be filled. Seat writes now go through
  `DatabaseService.assign_player_seat`; `/join` takes over a vacant seat.
- **Track O — dead tests and dead code landed as `v2.7.74`** and is archived in
  [`done_fixes.md`](done_fixes.md). The suite's 11 permanent skips are gone (0 skipped now —
  **a skip in a local run is unambiguously a missing DB**), three PNG-to-disk eyeball scripts
  and two tautological demo files with them; the three `generate_map` routes got real
  success-path tests; a dozen never-called methods, four unused arrow primitives (renders
  byte-identical) and `src/client.py` are removed.
- **Track N — deadlines are never imposed landed as `v2.7.72` and `v2.7.73`** (maintainer
  chose option (a), then asked for the command) and is archived in
  [`done_fixes.md`](done_fixes.md). The manual `process_turn` route no longer re-arms a
  hard-coded +24h; a deadline exists only when set explicitly — now possible from the bot
  with `/deadline <game_id> <hours|clear>` — and is spent when its phase is processed.
- **Track M — Concession releases the power's supply centres landed as `v2.7.71`** and is
  archived in [`done_fixes.md`](done_fixes.md). **Reverses a D3 design decision** ("concede
  never touches ownership"): a conceded power kept its centres, so next Winter the engine owed
  it builds, `/status` waited on the player who had just left, and a `BUILD` walked them back
  into a game the web client said they could not undo leaving.
- **Track L — No writes on a finished game landed as `v2.7.70`** and is archived in
  [`done_fixes.md`](done_fixes.md). A `COMPLETED` game used to accept orders, "process"
  turns (and DM everyone about it), record draw votes and let a power concede — the last of
  which removed its units from the final board. All four now raise `GameOverError` → 409 /
  DAIDE `REJ`, and `orders_status` waits on nobody.
- **Track K — Phase-aware order acceptance landed as `v2.7.69`** and is archived in
  [`done_fixes.md`](done_fixes.md). `validate()` now refuses an order whose kind has no
  meaning in the current phase (a move typed during a retreat phase, a build during a
  movement phase) with a reason naming the phase, instead of accepting it and letting the
  adjudicator drop it silently; `orders_status` (and so `require_all`, the bot's `/status`
  and the `/processturn` confirmation) waits only on powers that actually have something to
  order this phase. Found by a bug hunt, not by F1 — F1/F2 remain unchecked.
- **Track J — Split deployment (VPS bot/web + home API) landed as `v2.7.68`** and is archived
  in [`done_fixes.md`](done_fixes.md). The two-host layout itself was retired in Track V; its
  reliability contract (the bot's durable queue, `client_timestamp`, `Idempotency-Key`, the
  pulled `bot_outbox`) stays, because the API is still down during every deploy.
- **Every automated task in this tracker is done again.** Tracks A–E and G–V are complete and
  archived in [`done_fixes.md`](done_fixes.md). **Only Track F remains, and it cannot be
  delegated to an agent** — it needs a live bot token and a human at a Telegram client.
- **Next action: F1**, whenever the maintainer has a Telegram client to hand. Nothing gates it
  and it gates nothing.
- **Track I (map legibility) was opened by the maintainer on 2026-07-30** as F2's first finding
  — the inline web map was unreadably small — and landed as `v2.7.66` (I1, full-size viewer)
  and `v2.7.67` (I2, renderer visuals). **F2 itself is still unchecked**: one defect found and
  fixed is not a judgement pass completed. Three further defects surfaced *while* fixing it,
  all recorded in I2's section rather than folded in silently — the largest being that the
  pending-orders map drew every support as cut and every hold as nothing.
- Completed this session, in order:
  **G1 → G3 → G4 → G5 → G2 → G6 → H1/H2 → G3a → I1 → I2** (`v2.7.58`–`v2.7.67`).
  Two of those turned out to be far larger than recorded, and both are worth knowing about:
  - **G1:** the bot's help text was wrong about more than province names. It also claimed
    `ARMY`/`FLEET` were accepted unit spellings (they are rejected outright) and marked
    `A Berlin HOLD` with a ❌ under an invented "don't mix short and long forms" rule — when
    `A BER HOLD` is in fact valid. The same block had been copy-pasted into three modules, so
    every copy was wrong at once. All user-facing order text now lives in one module.
  - **G3:** `notify_players` had **never sent a single notification in this project's history**.
    It read `telegram_id` off `PlayerModel`, which has no such column, so `getattr(..., None)`
    returned `None` every time and the send guard never passed. Every Telegram DM for every
    event — turn processed, deadline reminders, joins, broadcasts, game end — was dead code that
    raised nothing and logged nothing. The one test covering that path patched
    `notify_players` itself and so never executed its body.
- **The port is functionally finished.** The engine conforms to DATC, every phase is playable
  from both clients, a game can end by agreement or concession *and everyone is told*, a real
  DAIDE bot can play a turn over the wire, and a player can see what happened to their orders.
  What is unverified is whether the whole thing is *pleasant to use*, which is exactly Track F.
- **Suite baseline to hold (measured 2026-09-21 at `v2.7.80`, against a real local
  Postgres):** **1600 passed, 0 skipped, 10 xfailed**; ruff clean; engine coverage
  **93.8%** (floor 92), overall **72%** (floor 60). Track U net −19 (AWS tests out, split-layout
  tests in); Track T net +2; Track S added 1; Track R added 3; Track Q added 4; Track P added 9; Track O removed 21 tests and added 3;
  Track N added 17, M 1, L 13, K 27 (see
  `done_fixes.md`); Track J had it at 1548 at `v2.7.68`, Track I at 1491 at `v2.7.67`.
  Track I added 46: I2's `test_arrow_geometry.py` (29) and `test_pending_order_styling.py` (17);
  I1 was frontend-only. Tests added between `v2.7.56`'s 1333 and `v2.7.64`'s 1445: G1's 60 (`test_bot_help_text.py`), G3's 4
  (`test_turn_notifications.py`), G4's 10 (`test_support_order_menu.py`), G5's 12
  (`test_waiting_list.py`) plus a rewritten `test_telegram_waiting_list.py` (4 → 11) and two
  removed from `test_telegram_bot_enhanced.py`, G2's 11 (`test_province_display_names.py`),
  G6's 5 (`test_join_game_id_source_of_truth.py`), and G3a's 5
  (`test_draw_concede_notifications.py`).
- **Frontend baseline (measured for real at `v2.7.66` with a local Node 22):**
  **24 test files / 158 tests**, `tsc -b --noEmit` clean, `npm run build` green. I1 added
  `MapViewer.test.tsx` (20) and one `GameView` wiring test; before that, 23/137 since G2.
- **A migration landed this session:** `g5a1c2d3e4f5` (the `waiting_list` table). `alembic heads`
  must return exactly one head — see the carried-over fact below, which this one cost a
  round-trip to learn.

---

## Carried-over facts (do not lose these)

Hard-won, still load-bearing, and each one has already cost somebody a round-trip. Full
reasoning for every item is in [`done_fixes.md`](done_fixes.md).

- **10 DATC hard-tail xfails** (documented inline in `tests/datc/`): second-order convoy
  paradoxes 6.F.16/17/18/23/24, convoy-to-adjacent 6.G.7/11, beleaguered self-dislodge
  6.E.8/10, no-fleet-convoy 6.D.8. **Do not un-xfail without the iterative-Szykman resolver
  upgrade.** Out of scope.
- **DB-dependent tests skip silently** without `SQLALCHEMY_DATABASE_URL`. A local Postgres is
  configured for this repo (see `.env` and the `local-postgres-for-m6` memory). **A skip means
  something is wrong, not that the DB is unavailable — never trust a green local run without
  a DB.** If the system Postgres is not running and cannot be started, `initdb` + `pg_ctl` as
  the ordinary user on another port works (Track J was validated that way); note that
  `alembic/env.py` *overrides* `SQLALCHEMY_DATABASE_URL` from `.env`, so the migration must be
  run with `.env` moved aside.
- **The bot never talks to the server except through `api_client`, and player *writes* go
  through `api_post_reliable`** (Track J). It enqueues to a SQLite outbox before attempting
  and returns `delivered`/`queued`/`rejected`; the server side answers a repeated
  `Idempotency-Key` from its stored response and refuses order submissions whose
  `client_timestamp` predates `games.phase_started_at`. Server code notifies players only via
  `api/shared.notify_user` (a `bot_outbox` row the bot pulls) — there is no push and no port
  8081. A new write path that bypasses either half of this quietly reintroduces message loss.
  The bot image installs `requirements-bot.txt` only; `channels.py`'s lazy `api.shared`
  imports are the one tolerated seam and are caught.
- **No Node toolchain on this dev machine by default.** Frontend gates (`tsc`, Vitest,
  `npm run build`) cannot run until a local Node 22 is fetched, despite `CLAUDE.md`
  documenting them as normal gates. An agent that reports "could not run the frontend gates"
  is being honest, not lazy — install the toolchain and re-run them yourself. This works and
  needs no root (G2 used it to run the frontend gates for real):

  ```bash
  curl -fsSLO https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz
  tar xf node-v22.14.0-linux-x64.tar.xz
  export PATH="$PWD/node-v22.14.0-linux-x64/bin:$PATH"
  cd new_implementation/frontend && npm ci
  ```
- **Coverage floors:** engine ≥92% (`--include='src/engine/*'`), overall ≥60%. The engine
  floor has **under a point of headroom** and is deliberately not ratcheted tighter: a tighter
  floor makes ordinary dead-code deletion fail CI.
- **`format_order` renders fleets as `A`** unless passed an explicit `kind_by_province` map —
  it infers the unit letter from coast presence. This has now shipped as a user-visible bug
  **twice** (Track A's PR2 recorded it; Track E's E1 reintroduced it and E4 fixed it). The
  kind is genuinely absent from an engine `Order`, which references a `Location`, never a
  `Unit`, and is only recoverable from the board *before* adjudication. Any new code that
  renders order strings must pass the kind map.
- **`orders_by_unit` keys match builds and disbands as a *suffix*, not a prefix.** Keys are
  `f"{kind} {location}"` with coast (`"F STP/SC"`); the grammar is verb-first for builds and
  disbands (`D A PAR`, `BUILD F BRE`). `WAIVE` has no unit and appears only in the flat
  `orders` list.
- **Never write to an ORM row returned by a `DatabaseService` getter.** Those rows are
  detached once the getter's session closes, and `DatabaseService.commit()` is a documented
  no-op, so `row.x = y; db_service.commit()` is silently discarded. This has now bitten three
  routes (`POST /deadline`, `/quit`, `/replace` — the last two for the whole life of the
  project, see Track P). Add a DAL method that opens its own session and commits.
- **A route's generic `except Exception` must be preceded by `except HTTPException: raise`**
  if the `try` body raises one, or the route's own 404/403/400 comes out as a 500 with the
  real status embedded in the text. And **never assert `status_code in [..., 500]`** in a
  test — fifteen such assertions hid exactly this for the whole life of the project (Track Q).
- **`require_bot_or_user` proves the caller is *someone*, not *the person the request acts
  on*.** Any route that takes a `telegram_id` or `power` from the body must resolve the
  caller (`resolve_user_or_telegram`) and check membership/ownership itself, or use
  `require_bot_secret` when only the bot may call it. And **a check inside a
  `@cached_response` route runs only on cache misses** — auth there must be a dependency
  (Tracks R–T found five routes between them).
- **Every `datetime` column is a naive `TIMESTAMP`.** Use
  `persistence.database.utcnow_naive()`, which returns **naive UTC on purpose** — handing
  Postgres a tz-aware value makes it convert to the session timezone and store it shifted,
  which silently corrupted every deadline on non-UTC dev machines. Do not "modernize" it. New
  `datetime` columns must be `timestamptz` or normalize on write.
- **`Game.history` does not survive a `GameRepo` round-trip.** `GameService.load` builds
  `Game(map=..., state=...)` with no `history` argument, so it is always `()` after a reload.
  Anything that needs the pre-adjudication board must compute it *during* `process_turn` and
  persist it — reconstructing it afterwards is impossible.
- **Any frontend test touching a `/games/:id` page must wrap it in
  `<Routes><Route path="/games/:gameId" …>`.** A bare `MemoryRouter` leaves `useParams()`
  unresolved and silently tests the loading spinner. (The old `GameView.test.tsx` asserted
  nothing at all for this reason.)
- **When touching `src/rendering/`, compare rendered PNG bytes before and after.** Clear
  `Map.clear_map_cache()` and `/tmp/diplomacy_map_cache`, render board/orders/resolution PNGs
  through the real `GameService`/API-route functions, compare sha256. That check caught what
  the test suite could not, twice.
- **After adding an Alembic revision, check `alembic heads` returns exactly one head.** G5's
  first revision id collided with the existing `a1b2c3d4e5f7` (M6's state_json migration).
  Alembic does not fail on the duplicate — it emits a `UserWarning: Revision … is present more
  than once` and then `upgrade head` dies with "Multiple head revisions are present", which
  reads like a branching problem rather than a copy-pasted id. Also verify the migration
  round-trips (`upgrade` → `downgrade -1` → `upgrade`) against a real Postgres; CI runs against a
  fresh `postgres:14`, so a broken `downgrade` is invisible there.
- **Pushing to protected `main`:** a bare `git push origin main` is always rejected — the
  required checks (`test`, `frontend`, `security`) have never run on a brand-new SHA. Go
  through a PR, or push to a temp branch, wait for green on that SHA, then fast-forward.

## Execution model (for any agent-delegated task below)

Unchanged from Tracks A–E, and it earned its keep: **one Sonnet subagent per task, each in its
own git worktree against its own Postgres database; the driver re-runs every gate and reads
the whole diff before opening a PR.** That caught, across five tracks, an unbounded
memory-growth bug, two failing frontend tests an agent could not run, a production-safety bug
that would have minted an orphan game row on every deploy, and one wrong triage the driver
itself had handed down. **Re-run the gates yourself; do not merge on an agent's say-so.**

**Subagents do not edit this file** — with several agents in flight, concurrent edits to
`fix_plan.md` guarantee rebase conflicts. Agents report; the driver records.

```bash
# Local gates — run before every push (mirrors CI)
cd new_implementation && source venv/bin/activate
ruff check src/
PYTHONPATH=src python -m pytest tests/ -q --cov=src --cov-report=
coverage report --include='src/engine/*' --fail-under=92
coverage report --fail-under=60
cd frontend && npx tsc -b --noEmit && npm run test:run && npm run build
```

Merge procedure, branch-protection traps, and the `gh -R tenderi/diplomacy` requirement are in
`CLAUDE.md`; the two traps that each cost a round-trip (chaining `gh pr merge` with a branch
delete, and tagging a pre-rebase commit) are written up in `done_fixes.md`'s Track A section.

---

# Track Y — majority-vote deadline proposals

## Why this track exists

While reviewing Track X's findings the maintainer decided the channel
proposal-with-voting feature (X4's posting half, the tally half left as a
documented stub) wasn't worth finishing — nothing in the bot's real commands
ever exposed a way to trigger it in the first place — and redirected the same
effort at something with an actual precedent already asked for: letting a
table change the game's deadline by agreement instead of any one player doing
it unilaterally.

## Y0 — Remove the channel proposal-voting stub — **done, `v2.7.95`**

- [x] Deleted `post_proposal_with_voting`/`get_proposal_results` from
      `telegram_bot/channels.py`, `POST/GET .../channel/proposal[/{id}]` from
      `api/routes/channels.py`, the `vote_proposal_*` callback branch from
      `app.py`, and `tests/test_channel_voting.py` (which only tested the two
      removed functions). The rest of Track X4's channel-posting fix
      (broadcast/thread/timeline/dashboard/battle_results) is untouched — this
      only removes the one feature with a stub tally, not the pattern.

## Y1 — Majority-vote deadline proposals — **done, `v2.7.96`**

**Design**, settled with the maintainer before writing any code (there was no
existing precedent to default to — a draw vote requires unanimity, this
doesn't):

- **Majority, not unanimity**, of the same active-power population a draw
  vote's quorum already uses (non-eliminated, with a unit —
  `GameService.active_powers`, extracted from `_draw_quorum` so both share one
  definition of "who's still playing"). A yes-majority applies the proposal
  immediately; a no-majority (mathematically no yes-majority can still be
  reached) rejects it immediately, so a doomed proposal with no expiry set
  doesn't sit pending forever.
- **Any player may propose; only one proposal pending per game at a time** — a
  second attempt is refused (400) until the first resolves or its proposer
  withdraws it (`POST .../deadline/withdraw`, proposer-only).
- **An optional per-proposal vote expiry** (`vote_hours`, distinct from the
  deadline value itself, `hours`, being proposed). Omitted, the proposal never
  expires on its own, matching how a draw vote never does either. Set, and
  unreached by the time it passes, the scheduler's expiry sweep
  (`api.shared.expire_deadline_proposals`, called from `deadline_scheduler`
  alongside `process_due_deadlines`) fails it with nothing changed — the same
  "fails closed" choice as a majority-no.
- **The existing unilateral `POST .../deadline` is untouched.** Any single
  player can still set or clear the deadline outright, exactly as before
  (Track N); proposing is an alternative for a table that wants to decide
  together, not a replacement.

**Implementation:**

- [x] `games.pending_deadline_proposal` (JSON, nullable; migration
      `j8d4e5f6a7b8`): `{proposed_by, value_hours (null = "clear"), votes:
      {power: "yes"|"no"}, vote_deadline (null = no expiry), created_at}`.
- [x] `GameService.active_powers(game_id)` — public, wraps `_draw_quorum` so
      draw-vote quorum and deadline-proposal majority can't define "active
      power" two different ways.
- [x] `api.shared.propose_deadline` / `vote_on_deadline_proposal` /
      `withdraw_deadline_proposal` / `expire_deadline_proposals`, and three new
      routes (`POST .../deadline/{propose,vote,withdraw}`); `GET .../deadline`
      now also returns `pending_proposal`.
- [x] Bot: `/deadline <id> propose <hours|clear> [vote_hours]`,
      `/deadline <id> vote yes|no`, `/deadline <id> withdraw`, folded into the
      existing `/deadline` command (which needs the caller's *power* for these
      three, unlike plain set/clear, so it resolves it via
      `resolve_game_and_power` where the old path didn't bother). `HELP_TEXT`
      updated.
- [x] `tests/test_deadline_voting.py` (API-level: propose, majority accept,
      majority reject, clearing via vote, withdraw authorization, per-power
      vote authorization, expiry sweep, no-expiry-never-fires) and
      `tests/test_deadline_command.py`'s new `TestDeadlineProposeVoteWithdraw`
      (bot-level, mocked HTTP). Verified the majority-threshold tests are not
      vacuous by mutation (`n // 2 + 1` → `n // 2`: two tests failed as
      expected, then reverted).

---

## Y2 — Deadline-proposal hardening (bug hunt) — **done, `v2.7.97`**

Found by probing the Track Y routes over the real local Postgres (scratchpad script driving
`TestClient`), not by review. Each finding below was reproduced before it was fixed.

- [x] **`hours` and `vote_hours` were never range-checked** by the API (the bot checked
      `hours` but not `vote_hours`, and a browser caller skips the bot entirely).
      `hours: -5`, once voted through, stored a deadline five hours in the past — the
      scheduler processes such a turn on its next tick. `hours: NaN` and
      `vote_hours: Infinity` were 500s on propose. `hours: 1e12` was accepted into the vote
      and then 500'd on the *deciding* yes — after `vote_on_deadline_proposal` had already
      cleared the proposal, so the majority's vote vanished with nothing applied and nobody
      told. Now `api.shared._check_proposal_hours`: finite, `> 0`, `≤ 720` (the bot's own
      30-day ceiling) → 400. The bot checks `vote_hours` too.
- [x] **Apply before clear.** The deciding vote now writes the deadline first and deletes
      the proposal second, so any failing write leaves it pending with its votes.
- [x] **An accepted proposal never re-armed the 10-minute reminder.** `POST .../deadline`
      resets `reminder_sent`; `_apply_deadline_proposal` did not, so a table that extended
      the deadline by vote after the old reminder fired got no reminder for the new one.
- [x] **Accepted means a time.** The accept responses now carry the applied `deadline`, and
      the notifications and the bot's replies say "deadline now 2026-09-25 07:33 UTC"
      instead of "now 12.0h" (twelve hours from *when*?). The bot falls back to
      "12.0h from now" if it meets an older API mid-deploy.
- [x] **A finished game took deadline writes** — propose, vote, and the unilateral
      `POST .../deadline` all returned 200 on a `completed` game, fanning out "deadline set"
      news about a game that is over. The scheduler ignored it (it only reads `active`
      games), so no turn was ever processed, but Track L's rule is "no writes on a finished
      game": all three now 409. Withdrawing a pending proposal stays allowed.

Tests: `test_deadline_voting.py` (7-case range parametrization, applied deadline returned,
reminder re-armed, finished game → 409, failed apply leaves the proposal pending) and
`test_deadline_command.py` (bad vote window refused before any HTTP, accepted reply shows
the time, older-API fallback). All but the ordering test were run against the pre-fix code
and failed there.

---

# Track X — Telegram bot command audit

## Why this track exists

The maintainer reported Help -> Run Perfect Demo Game failing with "Demo script not
found," and asked for every bot command, feature and instructive text to be checked
against what actually works. It found three unrelated things, each worse than the last.

## X1 — Help -> Run Perfect Demo Game: dead by construction — **done, `v2.7.92`**

- [x] `admin.run_automated_demo` shelled out to `examples/demo_perfect_game.py`, which
      imports the full engine (`engine.game`, `server.server.Server`). The bot's Docker
      image installs `requirements-bot.txt` only (`python-telegram-bot` + `requests`,
      deliberately no engine/SQLAlchemy/FastAPI) — this could never have worked in a
      deployed container, only ever "Demo script not found." Removed the function, its
      import, its `app.py` dispatch branch, and the menu button.

## X2 — The in-chat Admin menu: dead by a different construction — **done, `v2.7.92`**

- [x] Delete All Games / Recreate Admin User / System Status called `/admin/*` routes
      gated on `X-Admin-Token`. The bot never receives that secret — `api_client.py`
      only ever sends `X-Bot-Secret` — by design, per the security split `CLAUDE.md`
      documents (giving the bot container the admin token would be a real regression,
      not a bug fix). `POST /admin/recreate_admin_user` does not exist server-side at
      all, a second, independent reason that one specifically 404'd regardless of auth.
      Removed `show_admin_menu`, its three callback handlers, and the gating logic that
      had been copy-pasted into three places (`games.py`'s `/start`, `ui.py`'s
      `show_main_menu` and `refresh_keyboard`).

## X3 — Channel auto-posting has never once worked — **done, `v2.7.93`**

**Finding.** `/link_channel`'s confirmation text has promised "Maps will be posted
after each turn / Broadcasts will be forwarded / Turn notifications will be sent"
since the command existed. None of it has ever happened, silently, for two
independent reasons stacked on top of each other:

1. **Wrong process.** The posting functions live in `telegram_bot/channels.py` and
   only work when `_telegram_bot` (a module global) has been set — which happens
   exactly once, in the bot's own `app.py` `post_init`. The *callers* are all
   server-side (`api/shared.py`'s post-turn hook, `api/routes/messages.py`'s
   broadcast handler, every route in `api/routes/channels.py`), running in the
   separate `diplomacy_api` container, where `_telegram_bot` is permanently `None`.
   `post_map_to_channel` and friends each open with `if not _telegram_bot: return
   None` — no exception, nothing in the logs, just silently nothing sent.
2. **Wrong async convention, underneath that.** Even granting a live `Bot` instance,
   `post_map_to_channel` calls `_telegram_bot.send_photo(...)` with no `await`.
   `python-telegram-bot` has been an async library since v20 (`requirements-bot.txt`
   pins `>=22.0`); an unawaited call returns a coroutine object and does nothing.
   Every `test_channel_*.py` file passes because it sets `_telegram_bot` to a
   `unittest.mock.Mock` directly *in the test process* and calls the posting
   function synchronously — which exercises the formatting logic for real but
   can't catch either the cross-process gap or the missing `await`, since a `Mock`
   swallows both.

**Fix, for the two triggers that are actually reachable from a real bot command**
(turn processed, broadcast sent — exactly what `/link_channel` promises):

- [x] `api/shared._post_turn_to_channel` and `api/routes/messages.py`'s broadcast
      handler no longer import `telegram_bot.channels` at all. They read
      `channel_info["settings"]` directly (already fetched server-side) and call
      `db_service.enqueue_bot_notification(channel_id, message, kind="channel_text"
      | "channel_map", payload=...)` — the same durable, polled `bot_outbox` queue
      every player DM already uses. `BotOutboxModel.kind` was already documented as
      "`dm` today, so channel posts can join the same queue later without a schema
      change" — this is that later.
- [x] `telegram_bot/notifications.py`'s delivery loop gained `_send_outbox_item`,
      which dispatches on `kind`: `"channel_map"` fetches the image itself via
      `GET /games/{id}/map` (the API queues only `payload.game_id` — it has no
      filesystem in common with the bot container to hand a rendered file through)
      and `send_photo`s it; `"channel_text"` is a plain `send_message` with no
      `parse_mode` (a forwarded broadcast carries a player's raw, not
      markdown-safe, text — matches the existing DM path, which never used one for
      the same reason); `"dm"` is unchanged.
- [x] Verified against a live `uvicorn` instance over real HTTP (not `TestClient`,
      and not a mocked `Bot`): linked a channel, processed a turn, sent a
      broadcast, and confirmed the bot side fetches a genuine ~700 KB PNG and
      calls `send_photo`/`send_message` with the right arguments. Existing
      `test_channel_*.py` suites (unaffected — they test the untouched formatting
      functions) and `test_turn_notifications.py` still green; full suite 1634
      passed, 10 xfailed.

## X4 — Six more channel routes had the same wrong-process bug — **done, `v2.7.94`**

`api/routes/channels.py`'s `/channel/broadcast`, `/thread`, `/proposal`, `/timeline`,
`/dashboard`, `/battle_results` each did `from ...telegram_bot.channels import <fn>`
and called it directly — the identical wrong-process bug X3 fixed for the two
triggers a bot command can actually reach. Unlike X3 nothing currently calls these
routes (`channel_commands.py`'s real bot handlers only ever hit `.../channel/link`,
`GET .../channel`, and `.../channel/settings`), so no promised behaviour was
silently broken — these were unreachable REST endpoints, not something a player
could trigger and see fail.

- [x] All six now format server-side (reusing `channels.py`'s pure `format_*`
      functions and `utils.escape_markdown`, neither of which touch `_telegram_bot`)
      and queue onto `bot_outbox` with `kind="channel_text"` — generalized from X3's
      version to carry `payload.parse_mode`, `payload.buttons` (an inline keyboard,
      for the proposal's vote buttons), and `payload.reply_to_message_id` (manual
      broadcast threading), all server-decided. A new `kind="channel_create_thread"`
      covers forum-topic creation. Routes that used to return a real `message_id`/
      `thread_id` synchronously now return `"status": "queued"` and an `outbox_id`
      instead — there is no ID until the bot's next poll actually sends it.
- [x] Verified against the same live `uvicorn` setup X3 used: linked a channel, hit
      all six routes, confirmed six correctly-`kind`ed/payloaded rows, then ran the
      bot's `_send_outbox_item` against them with a mocked `Bot` and confirmed
      `send_message`/`create_forum_topic` calls with the right `parse_mode`,
      `reply_markup` (present only for the proposal), and thread name.
- [x] **Proposal voting's tally half deliberately left alone.** Posting the
      proposal (with vote buttons) now actually reaches the channel; tapping a
      button still only acknowledges (`app.py`'s `vote_proposal_*` callback has its
      own comment: `"will be enhanced with database"`) and
      `GET .../channel/proposal/{id}` still always answers zero votes in every
      category. That was already a documented stub before this fix, not a
      wrong-process bug — no vote is recorded anywhere to route correctly. Building
      a real tally (a votes table, a write from the callback, a read here) is a
      feature to build, not a channel-posting bug; left open for whoever picks it up.
- [x] `_telegram_bot.send_photo(...)`'s missing `await` (and its siblings, found
      while diagnosing X3) is moot for every path fixed here and in X3 — none of
      them call the old `telegram_bot.channels` send functions any more, only the
      pure formatters. It would only resurface if the proposal-voting tally (above)
      or some future caller went back to calling `channels.py`'s post functions
      directly instead of going through `bot_outbox`.

**Superseded, `v2.7.95` (Track Y0):** the maintainer decided the proposal-voting
feature above wasn't worth finishing — the "left open for whoever picks it up" item
just above — and had it removed outright instead: `POST/GET .../channel/proposal[/{id}]`,
`post_proposal_with_voting`/`get_proposal_results`, and the `vote_proposal_*`
callback are gone. The other five routes fixed in this track (broadcast, thread,
timeline, dashboard, battle_results) are untouched and still work as described above.

---

# Track W — the rest of the pre-deletion audit of `old_implementation/`

## Why this track exists

`cfa8d93` (2026-09-09, never merged) audited `old_implementation/` feature-by-feature and
found items K0–K7 (its own numbering; see the Status entry above for why this file uses
"W"). Uncommitted code implementing K1's snapshot half, K2, K3, K4 and K5 was found sitting
on `origin/vps-split` on 2026-09-23, recovered, ported onto `main` (which had moved on
44 commits, including retiring the split-VPS deployment those commits were written against),
and landed as `v2.7.90` (Track W above). The rest of the audit is below, unchanged from
`cfa8d93` except renumbered and K1 split in two.

## W0 — Pre-deletion moves and deletion — **done, `v2.7.91`**

- [x] Moved `old_implementation/rules.pdf` to `new_implementation/docs/reference/rules.pdf`
      (`git mv`, history preserved) and repointed `docs/specs/diplomacy_rules.md`.
- [x] Updated the pointers: `CLAUDE.md` (repository layout, "Game rule questions"),
      `CODEBASE_OVERVIEW.md` (three places), and every docstring with a literal
      `old_implementation/<path>` reference (`src/server/daide/{clauses,wire}.py`,
      `tests/test_daide_tokens.py`, `tests/datc/*.py`) now reads
      `git show v2.7.68:old_implementation/<path>`, reproducible without the tree.
      Bare name-drops with no path (`session.py`, `tokens.py`, `test_daide_wire.py`, the
      historical Track W/`done_fixes.md` narrative) were left as prose — nothing there was a
      broken pointer.
- [x] Dropped the two `.gitignore` lines that only existed for the old tree (`diplomacy/games`,
      `!diplomacy/maps/convoy_paths_cache.pkl`).
- [x] Deleted `new_implementation/maps/mini_variant.json` — nothing read it
      (`grep -rln mini_variant` was empty outside itself).
- [x] `git rm -r old_implementation/`. Full suite green afterwards (1634 passed, 10 xfailed) —
      confirmed the audit's "nothing imports from it" finding for real, not just by grep.

## W1 — A deadline-triggered turn took no snapshot (bug, new code) — **done** (snapshot half fixed; re-arm half deliberately not ported)

**Finding (`cfa8d93`).** The two `process_turn` triggers had drifted again — the same class
of bug G3 fixed for notifications, one layer down: the manual route wrote a
`MapSnapshotModel` after every processed turn; the scheduler path
(`api/shared.py:process_due_deadlines`) wrote none, so `/history/{turn}` and the bot's
`/replay` had a permanent hole for every turn a missed deadline advanced.

- [x] **Snapshot half, fixed in `v2.7.90`.** `process_due_deadlines` now takes the same
      snapshot the manual route does, and invalidates the `/games/{id}/state` cache the
      manual route already did and the scheduler did not. Pinned by
      `test_both_triggers_snapshot_the_processed_turn` (`tests/test_turn_notifications.py`)
      and by snapshot assertions added to `tests/test_api_scheduler.py`.
- [x] **Deadline-rearm half, deliberately *not* ported.** `cfa8d93`'s fix also re-armed the
      deadline from `phase_length_seconds` (defaulting to 24h) after every processed turn.
      That directly reverses **Track N** (`v2.7.72`/`v2.7.73`), which decided — after this
      audit was written — that a deadline exists only when set explicitly. Track W keeps
      Track N: both triggers still clear the deadline unconditionally after processing;
      `phase_length_seconds` only ever arms one when a caller passes it to
      `POST /games/{id}/deadline` with no explicit `deadline` (see W2). Pinned by
      `test_manual_processing_never_imposes_a_deadline` (already existed, Track N) plus
      `test_deadline_route_can_arm_from_phase_length_explicitly` (new, Track W).

## W6 — Game options the old server had and the new one dropped without a decision

None of these were rejected anywhere in `done_fixes.md`; they simply were not ported.
**Each needs a maintainer yes/no** before any code — most are "not for this project", but
that should be written down once so the question stops being re-asked.

| Old feature | Where it lived | New equivalent | Decide |
|---|---|---|---|
| Private games (`registration_password`) | `CreateGame` | none — every game is joinable by anyone | |
| `n_controls`: start with fewer than 7 humans, rest as dummies in civil disorder (`CD_DUMMIES`) | `CreateGame`, `SetDummyPowers` | `required_powers = 7` hardcoded (`games.py`); a power with no player just holds forever, no start gate | |
| Process as soon as all orders are in (old default), with a per-player **wait flag** (`SetWaitFlag`, `ALWAYS_WAIT`/`REAL_TIME`) | server | manual `/processturn` (with a "missing powers" confirmation) or an explicit deadline; no wait flag | |
| Rule switches the old *engine* honoured: `BUILD_ANY`, `HOLD_WIN`, `SHARED_VICTORY`, `DONT_SKIP_PHASES`, `NO_CHECK`/`IGNORE_ERRORS`, `CIVIL_DISORDER` | `engine/game.py` | none; standard rules only | |
| Press rules `NO_PRESS` / `PUBLIC_PRESS` (a no-press game is a common variant) | server | messaging is always on | |
| `MULTIPLE_POWERS_PER_PLAYER` | server | one power per user per game | |
| Expert setup: `SetUnits`/`SetCenters`/`ClearUnits`/`SetGameState`, `state` at creation (puzzles, DATC-style scenarios by hand) | server | `POST .../restore/{snapshot_id}` only | |
| Delete one game (`DeleteGame`) | server | `/admin/delete_all_games` only (the waiting-list tests call the missing single delete a "documented residual") | |
| Observer / omniscient roles | server | spectator routes exist but are on the out-of-scope list | |

- [ ] Maintainer: fill the "Decide" column. Anything marked yes becomes its own task here;
      anything marked no moves to *Out of scope* below with the date.

## W7 — Order grammar accepts less than the old one (probably fine, but say so)

`README_COMMANDS.txt` listed "recommended" and "other possible" syntaxes. The new parser
(`engine/orders/parser.py`, probed 2026-09-09) accepts every *recommended* form and rejects
these alternates: unit-less orders (`PAR H`, `IRI - MAO`, `WAL S LON`, `NWG C NWY - EDI`),
verb-first retreats/removals (`RETREAT IRO - MAO`, `REMOVE F LIV`), and explicit multi-hop
convoy routes (`IRI - MAO - NAO - NWG`). Full province names were rejected by design in G1.

- [ ] Decide once: keep the grammar strict (one canonical form, which is what the bot's
      interactive order UI and `legal_orders` emit anyway — the recommended answer), or accept
      unit-less orders by inferring the unit from the board. If strict, add the rejected
      forms to `help_text.py`'s "not accepted" examples so `tests/test_bot_help_text.py`
      pins it.

## Definition of done (Track W)

- [x] W0 done (`v2.7.91`): `old_implementation/` removed, `rules.pdf` relocated, every
      pointer updated, suite green.
- [ ] W6's table has a decision in every row.
- [ ] W7: either landed or moved under *Out of scope* with the maintainer's decision.

---

# Track F — Manual acceptance (maintainer-only)

## Why this track exists

No automated test spans a real human playing a real game. This is Track A's original
acceptance criterion, never completed, plus the human judgement pass Track E's restructured
web UI never received. It needs a live bot token and a human at a Telegram client, so **it
cannot be delegated to an agent** — it is the maintainer's to run.

Both clients are believed to work: every phase has automated coverage, and E1–E4 shipped the
results UI. What is genuinely unverified is whether the whole thing is *pleasant and coherent*
to use, which no test asserts.

## F1 — End-to-end play-through, both clients

- [ ] `PYTHONPATH=src python -m server.telegram_bot` starts (true since PR1, but confirm).
- [ ] Start the API; create a game, fill 7 powers; `/map` returns a PNG in Telegram.
- [ ] Order a deliberate dislodgement (A PAR–BUR supported, vs. A MUN–BUR); process.
- [ ] Phase `S1901R`: the browser shows retreat options for the dislodged unit only; Telegram
      `/selectunit` offers retreats. Submit one, process — it takes effect.
- [ ] Play to `W1901A` with a captured centre. Both clients show exactly `delta` build slots
      with real home-centre options, and a power at `delta == 0` shows none. Submit a build,
      process — the unit appears on the map.
- [ ] **Done when:** every box above is checked, and any defect found is **filed as a new
      track in this file** rather than fixed silently mid-session. (Tracks G and I, which held
      exactly this kind of finding, are complete and archived in
      [`done_fixes.md`](done_fixes.md) — start a **"Track J"** rather than reopening either.
      Track I is precedent for how this goes: it began as one F2 complaint about map size and
      turned up three further renderer defects on the way.)

## F3 — Single-host follow-through (Track V)

- [x] First single-host deploy green (run `35850765609`, `b64a4ee`, 2026-09-23): all four
      containers healthy, `ensure_env.sh` replaced the token-valued bot secret and dropped
      the tunnel keys, `GET /bot/outbox` with the bot's secret → 200 and no poll failures
      since, `127.0.0.1/api/healthz` via nginx OK, API at 139 MB RSS, `backup.sh` run by hand
      wrote a 22-table dump. Ports 80/8000/8432/5432 all unreachable from the internet: the
      VPS `.env` has **`WEB_BIND=127.0.0.1`** (set before Track V), so the site is private
      until F4 (TLS) or until the maintainer sets `WEB_BIND=0.0.0.0` and allows TCP 80.
- [ ] Exercise the queue for real: `docker compose stop diplomacy_api`, send `/order` and
      `/message` from Telegram, check `/queue`, `docker compose start diplomacy_api`, confirm
      the delivered reports arrive and the message shows its original time.
- [ ] **Maintainer, at home:** stop the old game-layer stack on `kattotuuletin.local`
      (`cd ~/diplomacy/new_implementation && docker compose down` — keep the `pg_data`
      volume until sure; it held no games). p2p's own stack and tunnel there are untouched.
- [ ] **Maintainer:** delete the now-unused `DIPLOMACY_BOT_SECRET` repository secret
      (`gh secret delete DIPLOMACY_BOT_SECRET -R tenderi/diplomacy`); it held the Telegram
      token by mistake, and nothing reads it any more.
- [x] **Maintainer:** connect off-host backups — **done 2026-09-24.** Proton Drive via
      rclone 1.75.1 on the VPS, signed in to the maintainer's own paid Proton account (chosen
      over a backups-only account, accepting that the VPS holds a full-drive login). The first
      login failed with `422 ... /auth/v4/2fa` because `rclone config` only *stores* the 2FA
      code and the first real login came a day later; a fresh code passed as
      `--protondrive-2fa=<code>` on the first command fixed it. `proton:diplomacy-backups`
      held three dumps right after.

## F4 — TLS in front of the web frontend

- [ ] A hostname for the VPS, Caddy (or certbot + nginx) terminating TLS in front of
      `diplomacy_web`, `WEB_BIND=127.0.0.1`, and `DIPLOMACY_PASSWORD_RESET_BASE_URL` in the
      VPS `.env` set to the `https://` URL. The login form must not stay on plain HTTP once anyone but
      the maintainer uses it. Was "known infra gap" under *Out of scope* below; it now has a
      concrete place to live.

## F2 — Human judgement pass on the restructured web game screen

- [ ] Play the F1 game through the browser and judge the E2/E4 layout as a *player*: is the
      phase state unmistakable, does "what happened last turn" answer the question a player
      actually asks, is the mobile layout usable on a real phone?
- [ ] **Why this is separate from F1:** E1–E4's gates were automated tests, `tsc`, and a
      build. Nobody has ever rendered the page — the dev machine has no headless browser and
      no Node by default (see `no-node-toolchain-locally`). "The tests pass" is not "the
      screen is good", and Track E explicitly declined to claim the latter.
- [ ] **Done when:** the maintainer has an opinion on record here. Cosmetic complaints become
      new tasks in this file (see F1's note on where to put them); "it's fine" is a valid and
      useful outcome to write down.

---

## Definition of done (open work)

- [ ] **Track F:** a game plays end-to-end (movement, retreat, build) from both the browser
      and Telegram, run by a human, with F1's five steps checked off and F2's judgement
      recorded. **This is the only item here that an agent cannot do.**
- [ ] **Track W:** W0 done (`old_implementation/` removed, `v2.7.91`). W6's decision table
      filled in and W7 decided are the only items left, both maintainer-only.
- [x] **Track X:** complete, `v2.7.92`–`v2.7.94`. Proposal-vote tallying (a
      documented stub predating this track, not a wrong-process bug) was left
      unimplemented, then removed outright rather than finished (Track Y0).
- [x] **Track Y:** complete, `v2.7.95`–`v2.7.96`. Channel proposal-voting stub
      removed; majority-vote deadline proposals landed alongside the existing
      unilateral `/deadline` set/clear, unchanged.
- [x] Throughout: full suite green **with a DB**, ruff clean, coverage floors hold, CI green on
      `main`, every landed chunk committed and tagged per `CLAUDE.md`. Held for all eleven tasks
      landed this session (`v2.7.58`–`v2.7.67`), each as its own PR through the required checks.

Tracks A–E and G–I's acceptance criteria are recorded in [`done_fixes.md`](done_fixes.md).

## Out of scope

- The 10 DATC hard-tail xfails / iterative-Szykman resolver (a separate engine project, if
  ever — see "Carried-over facts").
- Tournaments, Discord, observer/spectator mode, AI-powered analysis (long-standing maintainer
  list — `tournaments.py`, `discord_bot/`, `run_discord_bot.py` are **kept for backward
  compatibility, not dead code**; don't extend, don't delete).
- Rendering redesign — new art, a new layout engine, or an interactive/zoomable frontend map
  component. G2 adds province *names* to client text; it does not restyle the board.
- The aspirational spec docs (`dashboard.md`, `visualization_spec.md` §10).
- Map variants beyond `standard`.
- HTTPS / TLS termination — a known infra gap. It was entangled with "is there a production
  server at all", which Track H settled: **there is not** (see `done_fixes.md`), so there is
  currently nothing to terminate TLS *on*. C2's brute-force limiting reduces the risk for
  whatever does run; it does not replace TLS, and standing the infrastructure back up should
  include it.
- **Deep DAIDE press-content parsing** (the full `ALY`/`XDO`/`PRP` negotiation grammar beyond
  syntax-checked opaque forwarding) — a **permanent** design limitation documented in
  `architecture.md`, not a gap awaiting work.

## Risks / notes

- **`src/rendering/`'s exception handling is deliberately narrow.** All 27 formerly blanket
  `except Exception` blocks were replaced with specific tuples (`v2.7.28`) so a genuine
  programming bug raises instead of being logged and handed back as a subtly wrong image.
  **Never widen one back**, and when touching rendering, compare PNG bytes before and after —
  that check caught what the suite could not.
- **Renderer output is byte-cached** (`/tmp/diplomacy_map_cache` plus in-memory). Clear it when
  eyeballing visual changes (`Map.clear_map_cache()` or delete the tmp dir), or you will
  compare two copies of the same stale image.
- **`visualization_config.json` is live** (since V0) — if arrow styling differs from an old
  screenshot, that is the intended restore, not a regression.
- **`maps/standard.map` and `engine/map_loader.py` are the sole topology, alias *and* display-name
  source.** Two agents editing them in parallel will conflict; sequence such tasks or share one
  worktree. (G1 and G2 were the scheduled pair here; both landed, G2 adding `display_names` from
  the `=` lines' left-hand side.)
- **Display names are not parseable aliases, deliberately.** `MapData.display_names` exists for
  client output only; `aliases` is what `parse_order` consults. Adding a full name to `aliases`
  would half-implement the full-name input G1 explicitly decided against — it would work for
  single-word provinces and fail for the 26 multi-word ones. `tests/test_province_display_names.py`
  asserts `aliases['berlin']` is still `None`.
