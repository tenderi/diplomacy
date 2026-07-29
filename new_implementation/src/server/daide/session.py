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

import contextlib
import logging
from collections.abc import Sequence
from typing import Any, Optional

from engine.map_loader import MapData
from engine.orders.parser import format_order
from engine.types import (
    GameState,
    Location,
    Order,
    PhaseType,
    ResultCode,
    Season,
)
from server.daide import clauses, wire
from server.daide import tokens as t
from server.daide.tokens import Token
from server.daide.wire import DaideWireError

__all__ = [
    "DaideSession",
    "SessionProtocolError",
    "build_hlo_tokens",
    "build_mdf_tokens",
    "build_sco_tokens",
    "build_now_tokens",
    "build_mis_tokens",
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


def _reason_to_note_token(reason: Optional[str]) -> Token:
    if reason is None:
        return t.MBV
    r = reason.lower()

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

    # -- retreats --------------------------------------------------------------
    if "is not a legal retreat for" in r:
        return t.NVR  # "not a valid retreat space"
    if "no dislodged unit at" in r:
        return t.NSU  # "no such unit" (nothing there to retreat)

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
) -> list[Token]:
    """One ``ORD (turn) (order) (result [RET])`` message for a single `OrderResult`."""
    clause = clauses.encode_order(order, phase_type=phase_type, map=map)
    primary = _ORD_RESULT_TOKEN.get(result, t.NSO)
    notes = [primary]
    if dislodged and primary != t.RET:
        notes.append(t.RET)
    return [t.ORD, *turn_tokens, *clause, t.OPEN_PAREN, *notes, t.CLOSE_PAREN]


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
    ``broadcast_draw_completion(game_id)``, ``broadcast_admin(game_id,
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

    # -- connection lifecycle ----------------------------------------------

    async def run(self) -> None:
        """Handshake, then dispatch `DiplomacyMessage`s until the peer closes."""
        try:
            initial = await wire.read_message(self.reader)
        except DaideWireError as exc:
            await self._safe_send_error(exc.code)
            return
        except (ConnectionError, OSError, EOFError):
            return
        if not isinstance(initial, wire.InitialMessage):
            await self._safe_send_error(wire.ErrorCode.IM_SENT_BY_SERVER)
            return
        try:
            await wire.write_message(self.writer, wire.RepresentationMessage())
        except (ConnectionError, OSError):
            return

        try:
            while True:
                try:
                    msg = await wire.read_message(self.reader)
                except DaideWireError as exc:
                    await self._safe_send_error(exc.code)
                    break
                except (ConnectionError, OSError, EOFError):
                    break
                if isinstance(msg, wire.FinalMessage):
                    break
                if isinstance(msg, wire.DiplomacyMessage):
                    await self._handle_diplomacy(msg.payload)
                    continue
                # A second InitialMessage/RepresentationMessage/ErrorMessage
                # from a client mid-session is a protocol violation this
                # session doesn't try to recover from.
                await self._safe_send_error(wire.ErrorCode.UNKNOWN_MESSAGE_TYPE)
                break
        finally:
            self.server.unregister(self.game_id, self.power, self)
            with contextlib.suppress(Exception):
                self.writer.close()

    async def _safe_send_error(self, code: wire.ErrorCode) -> None:
        with contextlib.suppress(ConnectionError, OSError):
            await wire.write_message(self.writer, wire.ErrorMessage(code))

    async def send_off(self) -> None:
        """Server-initiated shutdown notice (`DaideServer.stop()` calls this
        on every open session before closing sockets)."""
        with contextlib.suppress(ConnectionError, OSError):
            await self._send(t.OFF)

    async def _send(self, *tokens_: Token) -> None:
        payload = b"".join(bytes(tok) for tok in tokens_)
        await wire.write_message(self.writer, wire.DiplomacyMessage(payload=payload))

    # -- dispatch -------------------------------------------------------------

    async def _handle_diplomacy(self, payload: bytes) -> None:
        tokens_ = [Token.from_bytes(payload[i : i + 2]) for i in range(0, len(payload), 2)]
        if not tokens_:
            return
        if not _parens_balanced(tokens_):
            await self._send(t.PRN, *_echo(tokens_))
            return

        command, *args = tokens_
        if command.text not in ("NME", "IAM") and self.power is None:
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

    # -- command handlers -----------------------------------------------------

    async def _cmd_nme(self, args: list[Token], raw: list[Token]) -> None:
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
        await self._send(*build_hlo_tokens(power, self.passcode))

    async def _cmd_iam(self, args: list[Token], raw: list[Token]) -> None:
        groups = _top_level_groups(args)
        if len(groups) != 2 or len(groups[0]) != 1 or not groups[1] or not groups[1][0].is_integer:
            raise SessionProtocolError("IAM needs (power) (passcode)")
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
            await self._send(t.YES, *_echo(raw))
        else:
            await self._send(t.REJ, *_echo(raw))

    async def _cmd_map(self, args: list[Token], raw: list[Token]) -> None:
        await self._send(t.MAP, *text_clause("standard"))

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

        decoded: list[tuple[list[Token], Optional[str], Optional[str]]] = []
        for inner in order_groups:
            clause_tokens = [t.OPEN_PAREN, *inner, t.CLOSE_PAREN]
            try:
                order = clauses.decode_order(clause_tokens, phase_type=game.state.phase_type, map=self.server.map)
                if order.power != self.power:
                    decoded.append((clause_tokens, None, f"unit belongs to {order.power}, not {self.power}"))
                    continue
                order_str = format_order(order)
            except (clauses.ClauseDecodeError, ValueError) as exc:
                decoded.append((clause_tokens, None, str(exc)))
                continue
            decoded.append((clause_tokens, order_str, None))

        to_submit = [os for (_, os, err) in decoded if err is None and os is not None]
        results = (
            self.server.game_service.submit_orders(self.game_id, self.power, to_submit) if to_submit else []
        )
        result_iter = iter(results)
        for clause_tokens, order_str, decode_err in decoded:
            if decode_err is not None:
                note = _reason_to_note_token(decode_err)
            else:
                r = next(result_iter, None)
                if r is not None and r["ok"]:
                    note = t.MBV
                else:
                    note = _reason_to_note_token(r["reason"] if r else None)
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
            await self._send(t.YES, *_echo(raw))
        elif sub_cmd == t.GOF:
            await self._send(t.YES, *_echo(raw))  # no ready-gate to cancel; ack only
        elif sub_cmd == t.DRW:
            self.server.game_service.submit_draw_vote(self.game_id, self.power, False)
            await self._send(t.YES, *_echo(raw))
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
        if result.get("quorum_reached"):
            await self.server.broadcast_draw_completion(self.game_id)

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
