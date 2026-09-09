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

- **Last updated:** 2026-09-09, at `v2.7.68` (PR #61 open, CI green).
- **Track K opened 2026-09-09: the pre-deletion audit of `old_implementation/`.** The
  maintainer asked whether the legacy tree can go. **Answer: yes, after K0** — nothing in it is
  imported, the engine is a clean-room rewrite, and removing it also removes the only AGPL code
  from a repo that ships no LICENSE. The audit compared it feature-by-feature against the new
  code and found **two real behavioural gaps (K1, K2), one test-coverage gap (K3), and a list
  of old features that were dropped without ever being decided on (K4–K7)**. K1 is a bug in
  the *new* code that the audit surfaced, not a legacy feature; it is the one item here worth
  doing before anything else.
- **Track J — Split deployment (VPS bot/web + home API) landed as `v2.7.68`** and is archived
  in [`done_fixes.md`](done_fixes.md). Production is now two Docker Compose stacks over the
  `p2p` WireGuard tunnel; player writes are queued durably on the VPS and server notifications
  in Postgres, so a dropped link never loses a message. The full operational guide is
  [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md). **Not yet done on the hosts:** actually running
  `install_home.sh` / `install_vps.sh` there, and TLS in front of the web frontend — both are
  the maintainer's, recorded under Track F below as F3/F4.
- **Tracks A–E and G–J are complete** and archived in [`done_fixes.md`](done_fixes.md).
  Open: **Track K** (agent-doable; K1 first, K0 whenever the maintainer says "delete") and
  **Track F** (maintainer-only — a live bot token, a Telegram client, and since Track J shell
  access to the two hosts).
- **Next action: K1**, then K0 on the maintainer's word, then F1.
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
- **Suite baseline to hold (measured 2026-07-30 on `main` at `v2.7.67`, against a real local
  Postgres):** **1491 passed, 11 skipped, 10 xfailed**, 2 warnings; ruff clean; engine coverage
  **93.44%** (floor 92), overall **69.49%** (floor 60).
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

# Track K — Retire `old_implementation/`: what the audit found (2026-09-09)

## Why this track exists

The maintainer asked whether `old_implementation/` (Philip Paquette's AGPL `diplomacy`
package: DATC engine, Tornado websocket server, Python client, React UI, DAIDE adapter,
webdiplomacy.net integration, 14 map variants) is safe to delete, and whether everything
relevant has been learned from it. It stays in git history either way.

**Verdict: safe to delete, once K0 is done.** Verified 2026-09-09 by reading code, not
docstrings:

- Nothing under `new_implementation/` imports from it. Every mention is a docstring or a spec
  cross-reference (`daide/{clauses,wire,session,tokens}.py`, `tests/datc/*.py`,
  `tests/test_daide_*.py`, `docs/specs/diplomacy_rules.md`, `CLAUDE.md`,
  `CODEBASE_OVERVIEW.md`).
- The engine is a clean-room rewrite (Track D's ground rules; DATC tests written from the
  spec, "semantics only, no code copied"). The port's gap analysis (Track C, 2026-07-29) and
  Tracks A–J since have already mined it for behaviour.
- **Licensing improves.** The old tree is AGPL-3.0 (plus DPjudge MIT) and this repo ships no
  LICENSE; `CLAUDE.md` already says "read it, never copy from it". Deleting it makes the repo
  unambiguously the maintainer's own code.

The rest of this track is *what is not in the new code*. Everything below was checked against
`new_implementation/src` at `v2.7.68`; each item says where. Items are ordered by how much
they matter to a game actually being played, not by size.

## K0 — Pre-deletion moves (do these in the same commit as the `git rm`)

- [ ] **Move `old_implementation/rules.pdf` to `new_implementation/docs/reference/rules.pdf`.**
      `docs/specs/diplomacy_rules.md` is an OCR transcript that names the PDF as "the
      authority where the two disagree" and `CLAUDE.md` tells rule questions to cross-check it.
      It is the official rulebook, not AGPL code; it is the one file that must survive.
- [ ] Update the pointers: `CLAUDE.md` (repository layout, "Game rule questions"),
      `CODEBASE_OVERVIEW.md` (three places), `docs/specs/diplomacy_rules.md` line 5, and the
      docstrings in `src/server/daide/{clauses,wire,session,tokens}.py`,
      `tests/test_daide_tokens.py`, `tests/test_daide_wire.py`, `tests/datc/*.py`. Replace
      "see `old_implementation/...`" with "see `git show v2.7.68:old_implementation/...`" so
      the cross-check stays reproducible without the tree.
- [ ] Drop the two `.gitignore` lines that only exist for the old tree (`diplomacy/games`,
      `!diplomacy/maps/convoy_paths_cache.pkl`).
- [ ] Delete `new_implementation/maps/mini_variant.json` at the same time — nothing reads it
      (`grep -rn mini_variant src tests` is empty); it is a leftover from the same era.
- [ ] Do **not** copy `old_implementation/diplomacy/tests/network/{1,2,3}.json` (three
      recorded real games used as replay-regression fixtures). They are useful *as an idea*
      (K3) but they are data shipped under the AGPL tree; generate our own.

## K1 — A deadline-triggered turn drops the deadline and takes no snapshot (bug, new code)

**Finding.** The two `process_turn` triggers have drifted again — the same class of bug G3
fixed for notifications, one layer down:

- Manual `POST /games/{id}/process_turn` (`routes/games.py:262-281`) writes a
  `MapSnapshotModel` for the turn just processed and **re-arms the deadline to now+24h**.
- The scheduler path (`api/shared.py:process_due_deadlines`, line ~328) calls
  `game_service.process_turn`, then `update_game_deadline(id, None)`, and takes **no
  snapshot**.

So the first missed deadline in a game is also its last: the game has no deadline afterwards
until a human sets one with `/deadline`, and `GET /games/{id}/history/{turn}`,
`/map/history/{turn}` and the bot's `/replay` have a hole for every turn the scheduler
processed. The old engine re-armed its per-phase `deadline` on every phase, unconditionally.

- [ ] Move snapshot creation and deadline re-arm into the shared post-turn path
      (`notify_turn_processed` is the precedent: one fan-out, both triggers) so they cannot
      drift a third time. Re-arm from a per-game phase length (K2), defaulting to the current
      24 h.
- [ ] Extend `tests/test_turn_notifications.py`'s two-trigger comparison to assert the
      snapshot row and the new deadline exist after *both* triggers.

## K2 — No per-game phase length; 24 h is hardcoded

`CreateGameRequest` (`routes/games.py:28`) takes `map_name` and `initial_phase` only. The old
`CreateGame` took `deadline` (seconds per phase, default 300) and re-applied it every phase;
the new code sets 24 h once on start (`games.py:279`) and on manual processing. There is no
way to run a fast game (10-minute phases) or a slow one (48 h) without a human re-setting
`/deadline` after every turn.

- [ ] `games.phase_length_seconds` (nullable = "no automatic deadline"), set at creation and
      editable via the existing `/deadline` route; the shared post-turn path (K1) re-arms
      from it. Surface it in `/games/create` (bot and web) and in `/status`.

## K3 — Tests: DATC 6.A gaps, the old 6.K cases, and no full-game replay regression

- [ ] **DATC 6.A.4, 6.A.6–6.A.12 have no named test.** `tests/datc/test_datc_6a_basic.py`
      names 6.A.1/2/3/5 and then four generically-named tests; the old suite named all twelve.
      Some are almost certainly covered by validation tests elsewhere (6.A.9 fleets must
      follow coasts, 6.A.10 support on unreachable destination, 6.A.11/12 simple bounces),
      but "almost certainly" is exactly what the DATC ids exist to remove. Add one named test
      per case, cross-checked against `git show v2.7.68:old_implementation/diplomacy/tests/test_datc.py`.
- [ ] **Old 6.K.1–6.K.2** (Paquette's own additions, beyond the DATC's A–J): civil disorder
      when a power disbands *some* but not all of the units it must remove — the remainder
      must be auto-disbanded by the distance rule. `test_datc_6j_civil_disorder.py` covers
      6.J.1–11 (all-or-nothing); the partial case is untested. Add it.
- [ ] **No recorded-game replay regression.** The old suite replayed three real games
      (`tests/network/{1,2,3}.json`, ~900 KB) through the server and diffed every phase.
      Nothing in the new suite plays more than a handful of phases against fixed expected
      states. Record one full game through the new API (`simple_ai` self-play is enough),
      store it as a fixture, and assert the replay reproduces every phase's units, centres and
      resolution byte-for-byte. This is the test that would catch a resolver regression the
      DATC cases do not exercise in combination.

## K4 — Per-phase history is lossy

The old `get_phase_history` returned, for every past phase, the state, the orders, the
**results**, and the messages sent during it. The new code keeps:

- orders per turn — yes (`games.order_history`, `GET .../orders/history`);
- state per turn — only when a snapshot was taken (see K1);
- **results per turn — only the latest** (`games.last_resolution`; `turn_history` table
  exists but is never written — `grep -rn "TurnHistoryModel(" src` is empty);
- **messages — no phase attribution** (`MessageModel` has `timestamp` only; the old
  `Message` carried `phase`).

So "what happened in turn 3" is answerable for the board and the orders but not for the
outcomes, and "what was said during F1902M" is not answerable at all. The web client's
results panel (`GameView.tsx`, E4) reads `last_resolution` only.

- [ ] Persist the resolution per turn (write `turn_history`, or a `resolutions` JSON column
      keyed like `order_history`), and expose `GET .../history/{turn}` with orders +
      resolution + snapshot together.
- [ ] Add `messages.phase_code` (stamped from the game's phase at send time — note the bot
      now sends `client_timestamp`, so stamp from the phase that was current *then*, i.e.
      compare against `phase_started_at`).

## K5 — Saved-game export/import

Old: `utils/export.py` (`to_saved_game_format` / `from_saved_game_format`), a stable JSON
format, and "Load a game from disk" in the web UI; also how the K3 fixtures were made. New:
`grep -rln "saved_game\|export" src` is empty. A game cannot leave the database or be shared
as a file. Depends on K4 for the format to be complete.

- [ ] `GET /games/{id}/export` (JSON: map, players, every phase's state/orders/resolution/
      messages) and an admin-only `POST /games/import`. Then K3's fixture is just an export.

## K6 — Game options the old server had and the new one dropped without a decision

None of these were rejected anywhere in `done_fixes.md`; they simply were not ported.
**Each needs a maintainer yes/no** before any code — most are "not for this project", but
that should be written down once so the question stops being re-asked.

| Old feature | Where it lived | New equivalent | Decide |
|---|---|---|---|
| Private games (`registration_password`) | `CreateGame` | none — every game is joinable by anyone | |
| `n_controls`: start with fewer than 7 humans, rest as dummies in civil disorder (`CD_DUMMIES`) | `CreateGame`, `SetDummyPowers` | `required_powers = 7` hardcoded (`games.py:634`); a power with no player just holds forever, no start gate | |
| Process as soon as all orders are in (old default), with a per-player **wait flag** (`SetWaitFlag`, `ALWAYS_WAIT`/`REAL_TIME`) | server | manual `/processturn` (with a "missing powers" confirmation) or the 24 h deadline; no wait flag | |
| Rule switches the old *engine* honoured: `BUILD_ANY`, `HOLD_WIN`, `SHARED_VICTORY`, `DONT_SKIP_PHASES`, `NO_CHECK`/`IGNORE_ERRORS`, `CIVIL_DISORDER` | `engine/game.py` | none; standard rules only | |
| Press rules `NO_PRESS` / `PUBLIC_PRESS` (a no-press game is a common variant) | server | messaging is always on | |
| `MULTIPLE_POWERS_PER_PLAYER` | server | one power per user per game | |
| Expert setup: `SetUnits`/`SetCenters`/`ClearUnits`/`SetGameState`, `state` at creation (puzzles, DATC-style scenarios by hand) | server | `POST .../restore/{snapshot_id}` only | |
| Delete one game (`DeleteGame`) | server | `/admin/delete_all_games` only (the waiting-list tests call the missing single delete a "documented residual") | |
| Observer / omniscient roles | server | spectator routes exist but are on the out-of-scope list | |

- [ ] Maintainer: fill the "Decide" column. Anything marked yes becomes its own task here;
      anything marked no moves to *Out of scope* below with the date.

## K7 — Order grammar accepts less than the old one (probably fine, but say so)

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

## Recorded as *not* wanted (so nobody re-audits them)

Old features that exist only in the legacy tree and are, per the standing out-of-scope list
or by their nature, not coming across: the 13 non-standard map variants and the `USE`/`MAP`
map-file directives; the Tornado websocket protocol and the Python client library
(`diplomacy.client`) — REST + DAIDE cover programmatic play; the webdiplomacy.net
integration; SVG output from the renderer (the new renderer emits PNG); the Sphinx docs;
observer/omniscient games beyond the existing spectator routes; DAIDE press parsing
(permanent, see `architecture.md`).

## Definition of done (Track K)

- [ ] K1 fixed with the two-trigger test extended.
- [ ] K0 done in the same commit that removes `old_implementation/`, `rules.pdf` relocated,
      every pointer updated, suite green.
- [ ] K6's table has a decision in every row.
- [ ] K2–K5, K7: either landed or moved under *Out of scope* with the maintainer's decision.

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

## F3 — Bring the split deployment up on the two hosts (Track J follow-through)

- [ ] On `kattotuuletin.local`: `./install_home.sh`, fill `.env`, `docker compose up -d`,
      confirm `curl http://10.8.0.2:8000/healthz` from the VPS.
- [ ] On the VPS: `./install_vps.sh`, `TELEGRAM_BOT_TOKEN` + the printed bot secret,
      `docker compose -f docker-compose.control.yml up -d`; confirm TCP 80 is permitted by the
      UpCloud network firewall (separate from `ufw`).
- [ ] Exercise the queue for real: stop `wg-quick@wg0` at home, send `/order` and `/message`
      from Telegram, check `/queue`, restart the tunnel, confirm the delivered reports arrive
      and the message shows its original time.
- [ ] Decide what to do with the home server's existing p2p `docker-compose.yml` stack: both
      stacks bind the tunnel address on different ports (8081 vs 8000), so they coexist.

## F4 — TLS in front of the web frontend

- [ ] A hostname for the VPS, Caddy (or certbot + nginx) terminating TLS in front of
      `diplomacy_web`, `WEB_BIND=127.0.0.1`, and `DIPLOMACY_PASSWORD_RESET_BASE_URL` at home
      set to the `https://` URL. The login form must not stay on plain HTTP once anyone but
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

- [ ] **Track K:** `old_implementation/` removed with K0's moves done, K1 fixed, and every
      K6 row decided. Agent-doable except the decisions.
- [ ] **Track F:** a game plays end-to-end (movement, retreat, build) from both the browser
      and Telegram, run by a human, with F1's five steps checked off and F2's judgement
      recorded. **This is the only item here that an agent cannot do.**
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
