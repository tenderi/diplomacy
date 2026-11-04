"""Per-connection DAIDE protocol state machine (Track D, D4).

One `DaideSession` per accepted TCP connection. `server.DaideServer` owns the
listener and the cross-connection registry (which power is claimed by which
session, for a given game); this module only knows how to speak the message
level of the protocol for a single connection and calls back into the
`DaideServer` (passed in as `server`, duck-typed -- see the attributes this
module actually touches below, listed to avoid a circular import with
`server.py`) for anything that needs to reach *other* sessions.

## Message-level clause splitting

A `DiplomacyMessage` payload is a flat token stream: a command token followed
by its arguments, where arguments are almost always a run of top-level
``( ... )`` groups (``NME (name) (version)``, ``SUB (order) (order) ...``,
``NOT (GOF)``, ...). `clauses.py`'s `_read_group` is the order-level
equivalent of this but is not exported (it is a private module helper), so
`_top_level_groups` below is a small, independent equivalent scoped to this
module's needs -- it repeatedly consumes one ``(...)`` group at a time from a
flat token list, same nesting-aware technique.

## The handshake

The standard DAIDE client-server sequence, after the IM/RM exchange:

    client NME ('name') ('version')  ->  server YES (NME ...), MAP ('STANDARD')
    client MAP / MDF (optional)      ->  server MAP ('STANDARD') / MDF (...)
    client YES (MAP ('STANDARD'))    ->  server HLO (power) (passcode) (LVL n), SCO, NOW
    client REJ (MAP ('STANDARD'))    ->  server OFF, power released, session closed

The power and passcode are assigned at NME (so a full game answers REJ (NME
...) at once); HLO waits for YES (MAP), as the spec has it. A reconnecting
client sends IAM (power) (passcode), gets YES (IAM ...) and then asks for
what it needs (`HLO`, `SCO`, `NOW`, ...); a client `HLO` re-sends HLO at any
time. `OBS` is REJ: observers are out of scope.

## THX order-note mapping

`_reason_to_note_token` maps an `engine.orders.validation.ValidationResult.reason`
string (or a `clauses.ClauseDecodeError` message) onto one of the 19
`tokens.THX_NOTE_TOKENS`. There is no 1:1 mapping -- THX's vocabulary predates
this engine's specific English messages -- so it is a small ordered table of
substring checks, most-specific first, each commented with *why* that token
was picked, falling back to `NSP` ("no such province") when nothing matches
(logged, not silently swallowed): most unmapped rejections in practice trace
back to an unresolvable location, making NSP the least-wrong generic signal
in THX's fixed vocabulary (there is no "invalid, unspecified" token).

## Scope limitations (documented here rather than silently)

- **`TME`** is implemented as an immediate query ("how many seconds are left
  right now"), which is this codebase's own convention -- `old_implementation`'s
  `TME` request is actually a *subscribe/cancel a future deadline push*
  feature (hence its `on_time_to_deadline_request` unconditionally `REJ`s the
  query shape), which this codebase does not implement at all (no scheduled
  push notifications exist here; `notify_game_processed` already pushes
  `NOW`/`ORD`/`OUT`/`SLO` after every processed turn, which covers the same
  need). "No deadline set" is reported as `TME (-1)`, a negative sentinel
  chosen because there is no dedicated DAIDE token for it and integers are the
  only free-form space TME's syntax allows.
- **`HST`** replays only the submitted order strings for the requested phase
  (from `GameService.order_history`), each tagged `SUC` -- the true
  per-order `ResultCode` for a *past* phase is not retained anywhere
  (`last_resolution` only holds the most recent one), and reconstructing the
  historical `SCO`/`NOW` snapshot for that phase is not implemented. A bot
  asking `HST` gets *what was ordered*, not *what happened* or *the board at
  the time*.
- **`NOT (SUB (order))`** (cancelling one specific order) is not supported;
  `NOT (SUB)` always clears *all* of the calling power's pending orders for
  the phase, matching `GameService.clear_orders`'s only granularity.
- **`GOF`/`NOT (GOF)`** are acknowledged (`YES`) but do nothing -- this
  codebase has no per-power "ready" gate; turn processing is triggered by the
  HTTP route or the deadline scheduler, never by a DAIDE go-flag.
- **`SND`/press** is syntax-checked (balanced parens, a valid recipient-power
  list) and relayed opaquely wrapped in `FRM` -- the `PRP`/`ALY`/`XDO`/...
  press grammar itself is never parsed, per Track D's Ground Rules. A
  recipient with no live session simply does not receive the message (no
  offline mailbox).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Sequence
from typing import Any, Optional

from engine.map_loader import MapData
from engine.orders.parser import format_order
from engine.types import (
    Convoy,
    GameState,
    Location,
    Move,
    Order,
    PhaseType,
    Resolution,
    ResultCode,
    Season,
)
from server.daide import clauses, wire
from server.daide import tokens as t
from server.daide.tokens import Token
from server.daide.wire import DaideWireError
from server.game_service import GameOverError, StaleGameError, kind_by_province_of

__all__ = [
    "DaideSession",
    "SessionProtocolError",
    "build_hlo_tokens",
    "build_mdf_tokens",
    "build_sco_tokens",
    "build_now_tokens",
    "build_mis_tokens",
    "build_ord_messages",
    "build_ord_tokens",
    "parse_phase_code",
    "text_clause",
    "DAIDE_LEVEL",
]

_logger = logging.getLogger("diplomacy.server.daide")

# This codebase does not implement DAIDE's language-level negotiation depth
# (the LVL 10 press-time-limit / partial-draw extensions) -- level 0 covers
# the base gameplay message set this module actually speaks.
DAIDE_LEVEL = 0
# The name `MAP` announces; the DAIDE spec's own spelling of the standard map.
MAP_NAME = "STANDARD"
# Commands a connection may send before it holds a power. MAP and MDF are
# static and harmless; everything else (OBS included: observers are out of
# scope) is REJ until NME or IAM succeeds.
_UNSEATED_COMMANDS = frozenset({"NME", "IAM", "MAP", "MDF"})

# DCSP's IM timer: a connection must complete its InitialMessage within this
# many seconds of being accepted, or it gets `IM_TIMER_EXPIRED` and is closed.
IM_TIMEOUT_SECONDS: float = 30.0
# Once a frame's first byte has arrived, the rest of it must follow within
# this many seconds; a peer that stalls mid-frame is closed. Idling *between*
# frames is never timed (a bot may wait a whole phase for the next NOW).
FRAME_TIMEOUT_SECONDS: float = 30.0

# What writing to a peer's dead transport raises: a reset/broken pipe, or
# uvloop's `RuntimeError` ("unable to perform operation on <TCPTransport
# closed=True>"). `_send` turns the latter into a ConnectionResetError, so
# callers only ever need this tuple.
_TRANSPORT_ERRORS = (ConnectionError, OSError)


class SessionProtocolError(ValueError):
    """A message's clause structure doesn't match what its command expects.

    Caught by the dispatch loop and turned into a `HUH` response -- distinct
    from `ClauseDecodeError`/`ValueError` raised *inside* order decoding
    (`SUB`), which are mapped to THX order-notes instead.
    """


# ---------------------------------------------------------------------------
# Small token-stream helpers (message-level clause splitting)
# ---------------------------------------------------------------------------


def _parens_balanced(tokens_: Sequence[Token]) -> bool:
    depth = 0
    for tok in tokens_:
        if tok == t.OPEN_PAREN:
            depth += 1
        elif tok == t.CLOSE_PAREN:
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _top_level_groups(tokens_: Sequence[Token]) -> list[list[Token]]:
    """Split a flat token sequence into consecutive top-level ``(...)`` groups.

    Every element returned is a group's *inner* tokens (parens stripped).
    Raises `SessionProtocolError` if ``tokens_`` isn't exactly a run of
    balanced top-level groups (a bare token between/outside groups, or an
    unterminated one).
    """
    groups: list[list[Token]] = []
    i, n = 0, len(tokens_)
    while i < n:
        if tokens_[i] != t.OPEN_PAREN:
            raise SessionProtocolError(f"expected '(' at position {i}, got {tokens_[i].text!r}")
        depth = 0
        start = i
        while i < n:
            if tokens_[i] == t.OPEN_PAREN:
                depth += 1
            elif tokens_[i] == t.CLOSE_PAREN:
                depth -= 1
                if depth == 0:
                    groups.append(list(tokens_[start + 1 : i]))
                    i += 1
                    break
            i += 1
        else:
            raise SessionProtocolError("unterminated '(' group")
    return groups


def _text_of_tokens(tokens_: Sequence[Token]) -> str:
    """Reconstruct a plain string from a run of tokens (free text is always
    encoded as one ASCII-escape token per character on the wire)."""
    return "".join(tok.text for tok in tokens_)


def text_clause(s: str) -> list[Token]:
    """A free-text string -> the DAIDE ``(char char ...)`` group `tokens.Token`
    falls back to per-character ASCII escapes for anything not in the fixed
    vocabulary, which every plain-text character (letters, digits, spaces)
    hits."""
    return [t.OPEN_PAREN, *(Token.from_str(ch) for ch in s), t.CLOSE_PAREN]


def _echo(raw: Sequence[Token]) -> list[Token]:
    return [t.OPEN_PAREN, *raw, t.CLOSE_PAREN]


# ---------------------------------------------------------------------------
# Phase-code <-> (Season, PhaseType, year), the flat 3-letter-ish "S1901M"
# form GameState.phase_name / order_history use (distinct from clauses.py's
# turn_clause, which is the wire *token* group -- this is the plain string).
# ---------------------------------------------------------------------------

_SEASON_LETTER = {Season.SPRING: "S", Season.FALL: "F", Season.WINTER: "W"}
_LETTER_SEASON = {v: k for k, v in _SEASON_LETTER.items()}
_PHASE_LETTER = {PhaseType.MOVEMENT: "M", PhaseType.RETREAT: "R", PhaseType.ADJUSTMENT: "A"}
_LETTER_PHASE = {v: k for k, v in _PHASE_LETTER.items()}


def parse_phase_code(code: str) -> tuple[Season, PhaseType, int]:
    """Inverse of ``GameState.phase_name`` (e.g. ``"S1901M"`` -> (SPRING, MOVEMENT, 1901))."""
    if len(code) < 6 or code[0] not in _LETTER_SEASON or code[-1] not in _LETTER_PHASE:
        raise ValueError(f"{code!r} is not a phase code of the form 'S1901M'")
    return _LETTER_SEASON[code[0]], _LETTER_PHASE[code[-1]], int(code[1:-1])


# ---------------------------------------------------------------------------
# THX order-note mapping
# ---------------------------------------------------------------------------


def _reason_to_note_token(reason: Optional[str], phase_type: Optional[PhaseType] = None) -> Token:
    if reason is None:
        return t.MBV
    r = reason.lower()

    # -- an order of the wrong phase: "not the right season" ---------------------
    if "is not accepted during the" in r:
        return t.NRS
    # -- a retreat/disband for a unit that owes no retreat: "no retreat needed" --
    if "no dislodged unit at" in r or ("no unit to disband at" in r and phase_type is PhaseType.RETREAT):
        return t.NRN
    # -- a move to the unit's own province: not a move to an adjacent one -------
    if "its own province" in r:
        return t.FAR

    # -- engine.orders.validation._validate_build: exact-meaning matches -----
    if "is not a home supply center of" in r:
        return t.HSC  # "not a home supply centre"
    if "is not currently owned by" in r:
        return t.YSC  # "not your supply centre"
    if "is occupied" in r:
        return t.ESC  # "not an empty supply centre"
    if (
        "must name a valid coast" in r
        or "has no coasts to choose from" in r
        or "may not specify a coast" in r
        or "must name a coast" in r
    ):
        return t.CST  # "no coast specified" / wrong-coast family
    if "cannot build a fleet on landlocked" in r or "cannot build an army at sea" in r:
        return t.NAS  # "not at sea" -- wrong terrain for the unit kind being built

    # -- adjustment counts (validation's direction check, GameService's count) --
    if "has no build to" in r or ("waive" in r and r.endswith(" submitted")):
        return t.NMB  # "no more builds allowed": none owed, or more given than owed
    if "has no unit to disband" in r or ("disband" in r and r.endswith(" submitted")):
        return t.NMR  # "no more removals allowed": none owed, or more given than owed

    # -- retreats --------------------------------------------------------------
    if "is not a legal retreat for" in r:
        return t.NVR  # "not a valid retreat space"

    # -- movement / support / convoy -------------------------------------------
    if "is not adjacent to" in r:
        return t.FAR  # "not adjacent"
    if "cannot reach" in r:
        return t.FAR  # support/convoy range failure -- same "not adjacent" family
    if "a unit cannot support itself" in r:
        return t.FAR  # no exact token for self-support; FAR is the closest
        # "this order's geometry doesn't work" signal THX has.
    if "a convoying fleet must be in a sea space" in r:
        return t.NAS  # "not at sea"
    if "only a fleet may convoy" in r:
        return t.NSF  # "no such fleet"
    if "only an army may move via convoy" in r:
        return t.NSA  # "no such army"
    if "is not a coastal province" in r:
        return t.FAR  # convoy origin/dest not coastal -- geometry family, no exact token

    # -- ownership / existence --------------------------------------------------
    if "belongs to" in r and " not " in r:
        return t.NYU  # "not your unit"
    if "no unit to disband at" in r:
        return t.NSU
    if "no unit at" in r:
        return t.NSU
    if "is on coast" in r:
        return t.CST  # wrong coast named for the unit actually standing there

    # -- engine.orders.parser.OrderParseError / clauses.ClauseDecodeError shapes
    if "unknown province" in r:
        return t.NSP
    if "unit kind" in r or "missing unit location" in r or "no such" in r:
        return t.NSU

    _logger.warning("DAIDE THX: no note-token mapping for reason %r; defaulting to NSP", reason)
    return t.NSP


# ---------------------------------------------------------------------------
# ORD (post-resolution) result mapping
# ---------------------------------------------------------------------------

_ORD_RESULT_TOKEN: dict[ResultCode, Token] = {
    ResultCode.OK: t.SUC,
    ResultCode.BOUNCE: t.BNC,
    ResultCode.CUT: t.CUT,
    ResultCode.VOID: t.NSO,  # "no such order" -- closest match for an illegal/void order
    ResultCode.NO_CONVOY: t.DSR,  # convoy move failed for lack of a surviving fleet path
    ResultCode.DISLODGED: t.RET,  # "unit was dislodged and must retreat" (an annotation, not a verb)
    ResultCode.DISBAND: t.SUC,  # the removal itself completed as ordered/forced
    ResultCode.BUILD: t.SUC,
    ResultCode.WAIVE: t.SUC,
}


def build_ord_tokens(
    order: Order,
    result: ResultCode,
    dislodged: bool,
    phase_type: PhaseType,
    map: MapData,
    turn_tokens: Sequence[Token],
    *,
    kind_by_province: Optional[dict[str, str]] = None,
    power_by_province: Optional[dict[str, str]] = None,
    via_fleets: Sequence[Location] = (),
) -> list[Token]:
    """One ``ORD (turn) (order) (result [RET])`` message for a single `OrderResult`."""
    clause = clauses.encode_order(
        order,
        phase_type=phase_type,
        map=map,
        kind_by_province=kind_by_province,
        power_by_province=power_by_province,
        via_fleets=via_fleets,
    )
    primary = _ORD_RESULT_TOKEN.get(result, t.NSO)
    notes = [primary]
    if dislodged and primary != t.RET:
        notes.append(t.RET)
    return [t.ORD, *turn_tokens, *clause, t.OPEN_PAREN, *notes, t.CLOSE_PAREN]


def _convoy_route(move: Move, fleets: set[str], map: MapData) -> list[Location]:
    """The convoying fleets' provinces in order from ``move.unit`` to ``move.dest``
    (a path through ``fleets``); the fleets sorted by name when no path links them."""

    def nb(province: str) -> set[str]:
        return {loc.province for fl in map.fleet_locations(province) for loc in map.fleet_moves(fl)}

    def adjacent(a: str, b: str) -> bool:
        return b in nb(a) or a in nb(b)

    def walk(at: str, left: frozenset[str]) -> Optional[list[str]]:
        if not left:
            return [] if adjacent(at, move.dest.province) else None
        for nxt in sorted(left):
            if adjacent(at, nxt):
                rest = walk(nxt, left - {nxt})
                if rest is not None:
                    return [nxt, *rest]
        return None

    route = walk(move.unit.province, frozenset(fleets))
    return [Location(p, None) for p in (route if route is not None else sorted(fleets))]


def build_ord_messages(
    resolution: Resolution,
    board_units: Optional[Sequence[dict[str, Any]]],
    phase_type: PhaseType,
    map: MapData,
    turn_tokens: Sequence[Token],
) -> list[list[Token]]:
    """Every ``ORD`` of one adjudicated phase.

    ``board_units`` is the serialized board the orders were given on (the
    resolution's ``units``): fleets are encoded ``FLT`` and a supported or
    convoyed unit carries its real power. A convoyed move's ``VIA`` lists the
    fleets that ordered the convoy. ``None`` (a resolution stored before the
    board was kept) leaves the old, less exact encoding."""
    kinds: Optional[dict[str, str]] = None
    powers: Optional[dict[str, str]] = None
    if board_units is not None:
        kinds = {u["location"].split("/")[0]: u["kind"] for u in board_units}
        powers = {u["location"].split("/")[0]: u["power"] for u in board_units}
    convoys: dict[tuple[str, str], set[str]] = {}
    for r in resolution.results:
        o = r.order
        if isinstance(o, Convoy) and r.result is not ResultCode.VOID:
            convoys.setdefault((o.origin.province, o.dest.province), set()).add(o.unit.province)
    messages: list[list[Token]] = []
    for r in resolution.results:
        via: Sequence[Location] = ()
        if isinstance(r.order, Move) and r.order.via_convoy:
            fleets = convoys.get((r.order.unit.province, r.order.dest.province), set())
            via = _convoy_route(r.order, fleets, map)
        messages.append(
            build_ord_tokens(
                r.order,
                r.result,
                r.dislodged,
                phase_type,
                map,
                turn_tokens,
                kind_by_province=kinds,
                power_by_province=powers,
                via_fleets=via,
            )
        )
    return messages


# ---------------------------------------------------------------------------
# Response builders (pure -- reused by DaideServer's broadcasts too)
# ---------------------------------------------------------------------------


def build_hlo_tokens(power: str, passcode: int) -> list[Token]:
    power_token = t.POWER_TOKEN_BY_ENGINE_NAME[power]
    return [
        t.HLO,
        t.OPEN_PAREN,
        power_token,
        t.CLOSE_PAREN,
        t.OPEN_PAREN,
        Token.from_int(passcode),
        t.CLOSE_PAREN,
        t.OPEN_PAREN,
        t.LVL,
        Token.from_int(DAIDE_LEVEL),
        t.CLOSE_PAREN,
    ]


def build_mdf_tokens(map: MapData) -> list[Token]:
    """``MDF (powers) (provinces) (adjacencies)`` -- the full static map
    definition. Shape cross-checked against `old_implementation`'s
    `MapDefinitionResponse` (read-only reference, not copied -- see this
    package's module-level clean-room note in `tokens.py`/`clauses.py`):
    supply centres grouped by owning power (``UNO`` for the rest), a flat
    list of every other province, then per-province adjacency groups sourced
    entirely from `MapData` (never a second hardcoded topology)."""
    powers_clause: list[Token] = [t.OPEN_PAREN]
    for power in sorted(map.home_centers):
        powers_clause.append(t.POWER_TOKEN_BY_ENGINE_NAME[power])
    powers_clause.append(t.CLOSE_PAREN)

    sc_groups: list[Token] = [t.OPEN_PAREN]
    claimed: set[str] = set()
    for power in sorted(map.home_centers):
        centers = sorted(map.home_centers[power])
        if not centers:
            continue
        sc_groups.append(t.OPEN_PAREN)
        sc_groups.append(t.POWER_TOKEN_BY_ENGINE_NAME[power])
        for c in centers:
            sc_groups.append(t.daide_province_token(c))
            claimed.add(c)
        sc_groups.append(t.CLOSE_PAREN)
    unowned = sorted(map.supply_centers - claimed)
    sc_groups += [t.OPEN_PAREN, t.UNO, *(t.daide_province_token(c) for c in unowned), t.CLOSE_PAREN]
    sc_groups.append(t.CLOSE_PAREN)

    non_sc = sorted(map.provinces - map.supply_centers)
    non_sc_clause = [t.OPEN_PAREN, *(t.daide_province_token(p) for p in non_sc), t.CLOSE_PAREN]

    provinces_clause = [t.OPEN_PAREN, *sc_groups, *non_sc_clause, t.CLOSE_PAREN]

    adjacencies: list[Token] = [t.OPEN_PAREN]
    for province in sorted(map.provinces):
        entry: list[Token] = [t.daide_province_token(province)]
        army_dests = sorted(map.army_moves(province))
        if army_dests:
            entry += [t.OPEN_PAREN, t.AMY, *(t.daide_province_token(d) for d in army_dests), t.CLOSE_PAREN]

        if map.is_split_coast(province):
            for coast in map.coasts_of(province):
                loc = Location(province, coast)
                dests = sorted(map.fleet_moves(loc), key=lambda ln: (ln.province, ln.coast or ""))
                if not dests:
                    continue
                coast_token = t.COAST_TOKEN_BY_ENGINE_SUFFIX[coast]
                dest_tokens: list[Token] = []
                for d in dests:
                    dest_tokens.extend(clauses.location_to_clause(d))
                entry += [
                    t.OPEN_PAREN,
                    t.OPEN_PAREN,
                    t.FLT,
                    coast_token,
                    t.CLOSE_PAREN,
                    *dest_tokens,
                    t.CLOSE_PAREN,
                ]
        else:
            fleet_locs = map.fleet_locations(province)
            if fleet_locs:
                dests = sorted(map.fleet_moves(fleet_locs[0]), key=lambda ln: (ln.province, ln.coast or ""))
                if dests:
                    dest_tokens = []
                    for d in dests:
                        dest_tokens.extend(clauses.location_to_clause(d))
                    entry += [t.OPEN_PAREN, t.FLT, *dest_tokens, t.CLOSE_PAREN]

        adjacencies += [t.OPEN_PAREN, *entry, t.CLOSE_PAREN]
    adjacencies.append(t.CLOSE_PAREN)

    return [t.MDF, *powers_clause, *provinces_clause, *adjacencies]


def build_sco_tokens(ownership: dict[str, str], map: MapData) -> list[Token]:
    """``SCO (power centre centre ...) ... (UNO centre centre ...)`` -- current
    supply-centre ownership."""
    by_power: dict[str, list[str]] = {}
    owned: set[str] = set()
    for province, power in ownership.items():
        by_power.setdefault(power, []).append(province)
        owned.add(province)

    out: list[Token] = [t.SCO]
    for power in sorted(by_power):
        if power not in t.POWER_TOKEN_BY_ENGINE_NAME:
            continue  # defensive: ownership should only ever name a standard power
        out.append(t.OPEN_PAREN)
        out.append(t.POWER_TOKEN_BY_ENGINE_NAME[power])
        for province in sorted(by_power[power]):
            out.append(t.daide_province_token(province))
        out.append(t.CLOSE_PAREN)

    unowned = sorted(map.supply_centers - owned)
    out += [t.OPEN_PAREN, t.UNO, *(t.daide_province_token(p) for p in unowned), t.CLOSE_PAREN]
    return out


def build_now_tokens(state: GameState, map: MapData) -> list[Token]:
    """``NOW (turn) (unit) ... (dislodged-unit MRT (retreats)) ...`` -- current
    turn plus every unit's position, with dislodged units carrying their
    precomputed retreat options."""
    out: list[Token] = [t.NOW, *clauses.turn_clause(state.season, state.phase_type, state.year)]
    for u in sorted(state.units, key=lambda un: (un.power, un.province, un.location.coast or "")):
        out += clauses.unit_to_clause(u)
    for du in sorted(state.dislodged, key=lambda d: (d.power, d.province)):
        inner = clauses.unit_to_clause(du.unit)[1:-1]  # strip the unit clause's own outer parens
        retreat_tokens: list[Token] = []
        for loc in sorted(du.retreats, key=lambda ln: (ln.province, ln.coast or "")):
            retreat_tokens.extend(clauses.location_to_clause(loc))
        out += [t.OPEN_PAREN, *inner, t.MRT, t.OPEN_PAREN, *retreat_tokens, t.CLOSE_PAREN, t.CLOSE_PAREN]
    return out


def build_mis_tokens(game_service: Any, map: MapData, game_id: str, power: str) -> list[Token]:
    """``MIS (unit) ...`` / ``MIS (unit MRT (...)) ...`` / ``MIS (number)`` --
    units (or dislodged units) for ``power`` with no order yet this phase, or
    (adjustment) the outstanding build/disband delta.

    Simplification: the adjustment-phase count is the raw
    ``centers - units`` delta and does not subtract build/disband/waive
    orders already submitted this phase (unlike `old_implementation`'s
    running count) -- a bot polling `MIS` mid-submission will see the total
    owed, not the remaining owed. Documented, not silently approximated.
    """
    game = game_service.load(game_id)
    if game is None:
        return [t.MIS]
    state = game.state
    pending = game_service.pending_orders_parsed(game_id).get(power, [])
    ordered_locs = {getattr(o, "unit", None) for o in pending} - {None}

    if state.phase_type is PhaseType.MOVEMENT:
        out: list[Token] = [t.MIS]
        for u in sorted(state.units_of(power), key=lambda un: (un.province, un.location.coast or "")):
            if u.location in ordered_locs:
                continue
            out += clauses.unit_to_clause(u)
        return out

    if state.phase_type is PhaseType.RETREAT:
        out = [t.MIS]
        for du in sorted(
            (d for d in state.dislodged if d.power == power), key=lambda d: d.province
        ):
            if du.location in ordered_locs:
                continue
            inner = clauses.unit_to_clause(du.unit)[1:-1]
            retreat_tokens: list[Token] = []
            for loc in sorted(du.retreats, key=lambda ln: (ln.province, ln.coast or "")):
                retreat_tokens.extend(clauses.location_to_clause(loc))
            out += [t.OPEN_PAREN, *inner, t.MRT, t.OPEN_PAREN, *retreat_tokens, t.CLOSE_PAREN, t.CLOSE_PAREN]
        return out

    delta = len(state.centers_of(power)) - len(state.units_of(power))
    return [t.MIS, t.OPEN_PAREN, Token.from_int(max(-8192, min(8191, delta))), t.CLOSE_PAREN]


# ---------------------------------------------------------------------------
# The session itself
# ---------------------------------------------------------------------------


class DaideSession:
    """One TCP connection's worth of DAIDE protocol state.

    ``server`` is duck-typed to `server.DaideServer` (not imported here, to
    avoid a circular import -- `server.py` imports *this* module). The
    attributes/methods this class actually calls on it: ``game_service``
    (a `GameService`), ``map`` (a `MapData`), ``current_game_id`` (a
    non-raising ``Optional[str]`` property -- ``None`` until a game has
    actually been created), ``ensure_game_id() -> str`` (creates the game on
    first successful `NME`, not before -- see `DaideServer.start()`'s
    docstring for why eager creation is actively harmful for this repo's
    deploy pipeline), ``assign_power(game_id) -> Optional[str]``,
    ``register(game_id, power, session) -> int``, ``try_reclaim(game_id,
    power, passcode, session) -> bool``, ``unregister(game_id, power,
    session) -> None``, ``deadline_seconds(game_id) -> Optional[int]``,
    ``draw_voted(game_id, power, vote, result)``, ``broadcast_admin(game_id,
    from_name, message_tokens, exclude)``, ``relay_press(game_id, from_power,
    to_powers, message_tokens)``.

    ``self.game_id`` starts out ``None`` (mirroring the server's
    ``current_game_id`` at construction time -- already a real id if this is
    a second-or-later connection after some earlier session's `NME` created
    one) and is only ever set to a real id by a successful `_cmd_nme`/
    `_cmd_iam`, at which point `self.power` is set in the same breath -- every
    other command handler runs only once `self.power is not None` (the
    dispatch gate in `_handle_diplomacy`), so by the time any of them read
    ``self.game_id`` it is guaranteed to be a real id, not `None`.
    """

    def __init__(self, reader: Any, writer: Any, server: Any) -> None:
        self.reader = reader
        self.writer = writer
        self.server = server
        self.game_id: Optional[str] = server.current_game_id
        self.power: Optional[str] = None
        self.client_name: str = ""
        self.client_version: str = ""
        self.passcode: Optional[int] = None
        # The standard handshake (module docstring, "The handshake"): NME seats
        # the power and answers YES (NME ...) + MAP; HLO/SCO/NOW wait for the
        # client's YES (MAP ...). True once HLO has been pushed (or after IAM).
        self.welcomed = False
        # Set by a handler that ends the session (REJ (MAP ...)); the dispatch
        # loop returns after that message.
        self.closing = False

    # -- connection lifecycle ----------------------------------------------

    async def run(self) -> None:
        """Handshake, then dispatch `DiplomacyMessage`s until the peer closes.

        Nothing a client sends can raise out of here: a framing violation
        gets the matching DCSP `ErrorMessage` and a clean close, logged at
        warning; a dead transport just ends the session. Whatever happens,
        the session is unregistered and its socket closed on the way out.
        """
        try:
            if await self._handshake():
                await self._dispatch_loop()
        finally:
            self.server.unregister(self.game_id, self.power, self)
            with contextlib.suppress(*_TRANSPORT_ERRORS, RuntimeError):
                self.writer.close()

    def _peer(self) -> str:
        get_extra = getattr(self.writer, "get_extra_info", None)
        peer = get_extra("peername") if get_extra is not None else None
        return f"{peer} ({self.power or 'no power'})"

    async def _protocol_error(self, code: wire.ErrorCode, detail: str) -> None:
        _logger.warning("DAIDE %s: closing on %s (0x%02X): %s", self._peer(), code.name, code.value, detail)
        await self._safe_send_error(code)

    async def _handshake(self) -> bool:
        """Read the client's InitialMessage and answer the RepresentationMessage.
        Returns whether the session may proceed to message dispatch."""
        try:
            async with asyncio.timeout(IM_TIMEOUT_SECONDS):
                initial = await wire.read_message(self.reader, frame_timeout=FRAME_TIMEOUT_SECONDS)
        except TimeoutError:
            await self._protocol_error(wire.ErrorCode.IM_TIMER_EXPIRED, f"no IM within {IM_TIMEOUT_SECONDS} s")
            return False
        except DaideWireError as exc:
            await self._protocol_error(exc.code, str(exc))
            return False
        except (*_TRANSPORT_ERRORS, EOFError):
            return False
        if isinstance(initial, wire.FinalMessage):
            return False
        if isinstance(initial, wire.ErrorMessage):
            self._log_peer_error(initial)
            return False
        if not isinstance(initial, wire.InitialMessage):
            await self._protocol_error(wire.ErrorCode.IM_NOT_FIRST_MESSAGE, f"first message was {type(initial).__name__}")
            return False
        try:
            await wire.write_message(self.writer, wire.RepresentationMessage())
        except _TRANSPORT_ERRORS:
            return False
        return True

    def _log_peer_error(self, msg: wire.ErrorMessage) -> None:
        # DCSP: the sender of an ErrorMessage closes the connection; answering
        # it with another one would only be written to a closing socket.
        code = msg.code.name if isinstance(msg.code, wire.ErrorCode) else "unknown code"
        _logger.warning("DAIDE %s: client sent ErrorMessage %s (0x%02X)", self._peer(), code, int(msg.code))

    async def _dispatch_loop(self) -> None:
        while True:
            try:
                msg = await wire.read_message(self.reader, frame_timeout=FRAME_TIMEOUT_SECONDS)
            except DaideWireError as exc:
                await self._protocol_error(exc.code, str(exc))
                return
            except (*_TRANSPORT_ERRORS, EOFError):
                return
            if isinstance(msg, wire.FinalMessage):
                return
            if isinstance(msg, wire.ErrorMessage):
                self._log_peer_error(msg)
                return
            if isinstance(msg, wire.InitialMessage):
                await self._protocol_error(wire.ErrorCode.MULTIPLE_IM_SENT, "a second InitialMessage")
                return
            if isinstance(msg, wire.RepresentationMessage):
                await self._protocol_error(wire.ErrorCode.RM_SENT_BY_CLIENT, "a RepresentationMessage from the client")
                return
            try:
                await self._handle_diplomacy(msg.payload)
            except _TRANSPORT_ERRORS:
                return  # our own peer went away while we answered it
            if self.closing:
                return

    async def _safe_send_error(self, code: wire.ErrorCode) -> None:
        with contextlib.suppress(*_TRANSPORT_ERRORS):
            await self._write(wire.ErrorMessage(code))

    async def send_off(self) -> None:
        """Server-initiated shutdown notice (`DaideServer.stop()` calls this
        on every open session before closing sockets)."""
        await self.deliver([t.OFF])

    async def deliver(self, *messages: Sequence[Token]) -> bool:
        """Send ``messages`` to this session on behalf of *another* one (a
        broadcast, relayed press, a turn's NOW/ORD fan-out).

        Never raises for a dead peer: if this session's transport is closed or
        closing, it is unregistered and closed, and ``False`` returned, so the
        caller goes on to the remaining sessions.
        """
        try:
            for tokens_ in messages:
                await self._send(*tokens_)
        except _TRANSPORT_ERRORS as exc:
            _logger.warning("DAIDE %s: dropping dead peer: %s", self._peer(), exc)
            self.server.unregister(self.game_id, self.power, self)
            with contextlib.suppress(*_TRANSPORT_ERRORS, RuntimeError):
                self.writer.close()
            return False
        return True

    async def _send(self, *tokens_: Token) -> None:
        payload = b"".join(bytes(tok) for tok in tokens_)
        await self._write(wire.DiplomacyMessage(payload=payload))

    async def _write(self, message: wire.Message) -> None:
        """Write one frame; a closed transport raises `ConnectionResetError`
        (never uvloop's `RuntimeError`)."""
        is_closing = getattr(self.writer, "is_closing", None)
        if is_closing is not None and is_closing():
            raise ConnectionResetError("transport is closing")
        try:
            await wire.write_message(self.writer, message)
        except RuntimeError as exc:
            raise ConnectionResetError(str(exc)) from exc

    # -- dispatch -------------------------------------------------------------

    async def _handle_diplomacy(self, payload: bytes) -> None:
        tokens_ = [Token.from_bytes(payload[i : i + 2]) for i in range(0, len(payload), 2)]
        if not tokens_:
            return
        if not _parens_balanced(tokens_):
            await self._send(t.PRN, *_echo(tokens_))
            return

        command, *args = tokens_
        if command.text not in _UNSEATED_COMMANDS and self.power is None:
            await self._send(t.REJ, *_echo(tokens_))
            return

        handler = self._HANDLERS.get(command.text)
        if handler is None:
            await self._send(t.HUH, t.OPEN_PAREN, command, t.ERR, *args, t.CLOSE_PAREN)
            return
        try:
            await handler(self, args, tokens_)
        except SessionProtocolError:
            await self._send(t.HUH, t.OPEN_PAREN, command, t.ERR, *args, t.CLOSE_PAREN)
        except (GameOverError, StaleGameError):
            # SUB / DRW / NOT(DRW) after the game has ended, or a SUB/DRW that
            # raced the turn being processed: well-formed, just not acceptable
            # (any more). REJ is DAIDE's answer for that; the alternative was an
            # unhandled exception tearing the session down.
            await self._send(t.REJ, *_echo(tokens_))

    # -- command handlers -----------------------------------------------------

    async def _cmd_nme(self, args: list[Token], raw: list[Token]) -> None:
        if self.power is not None:
            await self._send(t.REJ, *_echo(raw))  # one connection holds at most one power
            return
        groups = _top_level_groups(args)
        if len(groups) != 2:
            raise SessionProtocolError("NME needs (name) (version)")
        self.client_name = _text_of_tokens(groups[0])
        self.client_version = _text_of_tokens(groups[1])
        # The game is created here, on the first successful NME -- not by
        # DaideServer.start() or on merely accepting a connection. Idempotent
        # (a no-op reuse) once some earlier session's NME already created it.
        game_id = self.server.ensure_game_id()
        power = self.server.assign_power(game_id)
        if power is None:
            await self._send(t.REJ, *_echo(raw))
            return
        self.game_id = game_id
        self.power = power
        self.passcode = self.server.register(game_id, power, self)
        await self._send(t.YES, *_echo(raw))
        await self._send(t.MAP, *text_clause(MAP_NAME))

    async def _cmd_iam(self, args: list[Token], raw: list[Token]) -> None:
        groups = _top_level_groups(args)
        if len(groups) != 2 or len(groups[0]) != 1 or not groups[1] or not groups[1][0].is_integer:
            raise SessionProtocolError("IAM needs (power) (passcode)")
        if self.power is not None:
            await self._send(t.REJ, *_echo(raw))  # one connection holds at most one power
            return
        game_id = self.server.current_game_id
        if game_id is None:
            # No NME has ever succeeded on this listener -- no game, no
            # passcode was ever issued, nothing to reclaim. IAM never creates
            # a game itself (only NME does; see ensure_game_id()'s docstring).
            await self._send(t.REJ, *_echo(raw))
            return
        try:
            power = t.engine_power_name(groups[0][0])
        except ValueError:
            await self._send(t.REJ, *_echo(raw))
            return
        passcode = int(groups[1][0])
        if self.server.try_reclaim(game_id, power, passcode, self):
            self.game_id = game_id
            self.power = power
            self.passcode = passcode
            self.welcomed = True  # a reconnecting client asks for HLO/NOW/... itself
            await self._send(t.YES, *_echo(raw))
        else:
            await self._send(t.REJ, *_echo(raw))

    async def _cmd_map(self, args: list[Token], raw: list[Token]) -> None:
        await self._send(t.MAP, *text_clause(MAP_NAME))

    async def _cmd_hlo(self, args: list[Token], raw: list[Token]) -> None:
        """A client's ``HLO`` asks for its HLO again (after `IAM`, typically)."""
        if self.power is None or self.passcode is None:
            raise SessionProtocolError("HLO before a power was assigned")
        await self._send(*build_hlo_tokens(self.power, self.passcode))

    async def _cmd_yes(self, args: list[Token], raw: list[Token]) -> None:
        """``YES (MAP ('name'))`` accepts the map: push HLO, SCO and NOW, the
        standard end of the NME handshake. A repeat is ignored (a YES needs no
        answer). The client sends no other top-level YES."""
        if not self._is_map_reply(args):
            raise SessionProtocolError("the only YES a client sends is YES (MAP ('name'))")
        if self.welcomed:
            return
        self.welcomed = True
        await self._cmd_hlo([], raw)
        await self._cmd_sco([], raw)
        await self._cmd_now([], raw)

    async def _cmd_rej(self, args: list[Token], raw: list[Token]) -> None:
        """``REJ (MAP ('name'))``: the client cannot play this map. Release
        its power, say ``OFF`` and end the session."""
        if not self._is_map_reply(args):
            raise SessionProtocolError("the only REJ a client sends is REJ (MAP ('name'))")
        self.server.unregister(self.game_id, self.power, self)
        self.power = None
        self.closing = True
        await self._send(t.OFF)

    @staticmethod
    def _is_map_reply(args: list[Token]) -> bool:
        groups = _top_level_groups(args)
        return len(groups) == 1 and bool(groups[0]) and groups[0][0] == t.MAP

    async def _cmd_mdf(self, args: list[Token], raw: list[Token]) -> None:
        await self._send(*build_mdf_tokens(self.server.map))

    async def _cmd_sco(self, args: list[Token], raw: list[Token]) -> None:
        view = self.server.game_service.view(self.game_id)
        ownership = view["ownership"] if view else {}
        await self._send(*build_sco_tokens(ownership, self.server.map))

    async def _cmd_now(self, args: list[Token], raw: list[Token]) -> None:
        game = self.server.game_service.load(self.game_id)
        if game is None:
            await self._send(t.REJ, *_echo(raw))
            return
        await self._send(*build_now_tokens(game.state, self.server.map))

    async def _cmd_sub(self, args: list[Token], raw: list[Token]) -> None:
        game = self.server.game_service.load(self.game_id)
        if game is None:
            await self._send(t.REJ, *_echo(raw))
            return
        try:
            order_groups = _top_level_groups(args)
        except SessionProtocolError:
            await self._send(t.HUH, t.OPEN_PAREN, t.SUB, t.ERR, *args, t.CLOSE_PAREN)
            return

        if not order_groups:
            await self._send(t.HUH, t.OPEN_PAREN, t.SUB, t.ERR, t.CLOSE_PAREN)
            return

        decoded: list[tuple[list[Token], Optional[str], Optional[str]]] = []
        for inner in order_groups:
            clause_tokens = [t.OPEN_PAREN, *inner, t.CLOSE_PAREN]
            try:
                order = clauses.decode_order(clause_tokens, phase_type=game.state.phase_type, map=self.server.map)
                if order.power != self.power:
                    decoded.append((clause_tokens, None, f"unit belongs to {order.power}, not {self.power}"))
                    continue
                order_str = format_order(order, kind_by_province_of(game.state))
            except (clauses.ClauseDecodeError, ValueError) as exc:
                decoded.append((clause_tokens, None, str(exc)))
                continue
            decoded.append((clause_tokens, order_str, None))

        to_submit = [os for (_, os, err) in decoded if err is None and os is not None]
        results = (
            self.server.game_service.submit_orders(self.game_id, self.power, to_submit, merge=True)
            if to_submit
            else []
        )
        if to_submit:
            self.server.orders_changed(self.game_id)
        result_iter = iter(results)
        for clause_tokens, order_str, decode_err in decoded:
            if decode_err is not None:
                note = _reason_to_note_token(decode_err, game.state.phase_type)
            else:
                r = next(result_iter, None)
                if r is not None and r["ok"]:
                    note = t.MBV
                else:
                    note = _reason_to_note_token(r["reason"] if r else None, game.state.phase_type)
            await self._send(t.THX, *clause_tokens, t.OPEN_PAREN, note, t.CLOSE_PAREN)

    async def _cmd_not(self, args: list[Token], raw: list[Token]) -> None:
        groups = _top_level_groups(args)
        if len(groups) != 1 or not groups[0]:
            raise SessionProtocolError("NOT needs exactly one wrapped sub-command")
        sub_cmd = groups[0][0]
        if sub_cmd == t.SUB:
            # Cancelling one specific order isn't supported -- always clears
            # every pending order this power has submitted this phase (see
            # the module docstring's scope-limitation note).
            self.server.game_service.clear_orders(self.game_id, self.power)
            self.server.orders_changed(self.game_id)
            await self._send(t.YES, *_echo(raw))
        elif sub_cmd == t.GOF:
            await self._send(t.YES, *_echo(raw))  # no ready-gate to cancel; ack only
        elif sub_cmd == t.DRW:
            result = self.server.game_service.submit_draw_vote(self.game_id, self.power, False)
            await self._send(t.YES, *_echo(raw))
            await self.server.draw_voted(self.game_id, self.power, False, result)
        else:
            # Includes NOT(TME): this codebase has no scheduled TME push to
            # cancel (see the module docstring) -- REJ, matching
            # old_implementation's own unconditional REJ of TME's request shape.
            await self._send(t.REJ, *_echo(raw))

    async def _cmd_gof(self, args: list[Token], raw: list[Token]) -> None:
        await self._send(t.YES, *_echo(raw))

    async def _cmd_mis(self, args: list[Token], raw: list[Token]) -> None:
        await self._send(*build_mis_tokens(self.server.game_service, self.server.map, self.game_id, self.power))

    async def _cmd_tme(self, args: list[Token], raw: list[Token]) -> None:
        seconds = self.server.deadline_seconds(self.game_id)
        value = -1 if seconds is None else max(0, min(8191, seconds))
        await self._send(t.TME, t.OPEN_PAREN, Token.from_int(value), t.CLOSE_PAREN)

    async def _cmd_hst(self, args: list[Token], raw: list[Token]) -> None:
        """`HST (turn)` -- always `REJ`, beyond validating the clause's shape.

        Bigger scope-cut than the "partial implementation" this command was
        expected to get: `GameService.order_history` is keyed by an internal
        sequential turn *counter* (``"0"``, ``"1"``, ...,  the value
        `GameRepo.save_state` happened to be at when that phase was left
        behind), not by the season/year/phase-type a real `(turn)` clause
        names. Retreat and adjustment phases are only inserted into a game's
        S{y}M -> [S{y}R] -> F{y}M -> [F{y}R] -> [W{y}A] -> S{y+1}M sequence
        when that phase actually had dislodgements/adjustments owed, so the
        mapping from a phase *code* to a turn *counter* isn't a formula --
        it depends on history this codebase doesn't persist anywhere
        (`Game.history` is in-memory only; `GameService.load` always
        reconstructs a `Game` with an empty one). Building that index is a
        persistence-layer change, out of D4's scope (`GameRepo`/`database.py`
        are explicitly not this task's layer to touch -- see the task brief).
        A well-formed request is still acknowledged as a *rejection*, not
        silently dropped or answered with a guess.
        """
        groups = _top_level_groups(args)
        if len(groups) != 1:
            raise SessionProtocolError("HST needs (turn)")
        try:
            clauses.turn_from_clause([t.OPEN_PAREN, *groups[0], t.CLOSE_PAREN])
        except clauses.ClauseDecodeError:
            pass  # malformed or well-formed -- either way HST can't be served; REJ either way.
        await self._send(t.REJ, *_echo(raw))

    async def _cmd_drw(self, args: list[Token], raw: list[Token]) -> None:
        result = self.server.game_service.submit_draw_vote(self.game_id, self.power, True)
        await self._send(t.YES, *_echo(raw))
        await self.server.draw_voted(self.game_id, self.power, True, result)

    async def _cmd_adm(self, args: list[Token], raw: list[Token]) -> None:
        groups = _top_level_groups(args)
        if len(groups) != 2:
            raise SessionProtocolError("ADM needs (name) (message)")
        name_text = _text_of_tokens(groups[0])
        await self.server.broadcast_admin(self.game_id, name_text, groups[1], exclude=self)

    async def _cmd_snd(self, args: list[Token], raw: list[Token]) -> None:
        groups = _top_level_groups(args)
        if len(groups) < 2:
            raise SessionProtocolError("SND needs (power power ...) (press message)")
        to_powers: list[str] = []
        for tok in groups[0]:
            try:
                to_powers.append(t.engine_power_name(tok))
            except ValueError:
                raise SessionProtocolError(f"SND recipient {tok.text!r} is not a power token") from None
        message_tokens = groups[1]  # forwarded opaquely -- press grammar is not parsed (Ground Rules)
        await self._send(t.YES, *_echo(raw))
        await self.server.relay_press(self.game_id, self.power, to_powers, message_tokens)

    _HANDLERS: dict[str, Any] = {
        "NME": _cmd_nme,
        "IAM": _cmd_iam,
        "HLO": _cmd_hlo,
        "YES": _cmd_yes,
        "REJ": _cmd_rej,
        "MAP": _cmd_map,
        "MDF": _cmd_mdf,
        "SCO": _cmd_sco,
        "NOW": _cmd_now,
        "SUB": _cmd_sub,
        "NOT": _cmd_not,
        "GOF": _cmd_gof,
        "MIS": _cmd_mis,
        "TME": _cmd_tme,
        "HST": _cmd_hst,
        "DRW": _cmd_drw,
        "ADM": _cmd_adm,
        "SND": _cmd_snd,
    }
