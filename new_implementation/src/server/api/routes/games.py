"""
Game management API routes.

This module contains all endpoints related to game creation, state management,
player management (join/quit/replace), deadlines, snapshots, and history.
"""
from fastapi import APIRouter, HTTPException, Body, Depends, Header
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi.security import HTTPAuthorizationCredentials
from .auth import require_bot_or_user, resolve_user_or_telegram, get_current_user_optional, http_bearer
from .auth import _check_rate_limit, _hash_password, _record_attempt, _verify_password
from .orders import _authorize_power
from .. import shared as api_shared
from ..shared import (
    db_service, game_service, logger, scheduler_logger, is_admin_token, is_bot_secret,
    notify_players, notify_user, notify_turn_processed, get_process_turn_lock, game_buttons,
)
from ...legal_orders import legal_orders_for_power
from ...response_cache import cached_response, invalidate_cache
from persistence.game_repo import StaleGameError
from server.game_service import GameOverError, OrderError

router = APIRouter()

# --- Request Models ---
class CreateGameRequest(BaseModel):
    """Request model for creating a new game."""
    map_name: str = "standard"
    initial_phase: Optional[str] = None  # None or "Pregame" = lobby; "Movement" = start immediately (e.g. tests)
    # Stored for later use by POST .../deadline (a caller may arm a deadline
    # from it explicitly); does not itself arm a deadline at creation -- Track N
    # decided deadlines exist only when set explicitly.
    phase_length_seconds: Optional[int] = None
    # Powers to leave to civil disorder from the start (W9): nobody may join
    # them and nobody waits on them. At most six -- one seat stays human.
    dummy_powers: List[str] = []
    # W10: process each turn as soon as all orders are in (and nobody waits).
    auto_process: bool = False
    # W8: make the game private -- /join then needs this password (the creator is exempt).
    join_password: Optional[str] = None
    # The bot's way of saying who is creating the game (a browser caller is the
    # Bearer user); recorded as the game's creator.
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


class AutoProcessRequest(BaseModel):
    """Body for ``POST /games/{game_id}/auto_process`` (W10)."""
    enabled: bool
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


class WaitFlagRequest(BaseModel):
    """Body for ``POST /games/{game_id}/wait`` (W10)."""
    power: str
    waiting: bool = True
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


class SetDummyRequest(BaseModel):
    """Body for ``POST /games/{game_id}/dummies`` (W9)."""
    power: str
    dummy: bool = True
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None

class AddPlayerRequest(BaseModel):
    """Request model for adding a player to a game."""
    game_id: str
    power: str

class SetDeadlineRequest(BaseModel):
    deadline: Optional[datetime] = None
    # Change the recurring phase length at the same time (seconds; 0 = none).
    # Omitted leaves it as it is. A bare phase-length change with no explicit
    # deadline arms one from the new length immediately.
    phase_length_seconds: Optional[int] = None
    # The bot sends the caller's id (+ bot_secret, injected by api_post) so the
    # route can check they are in the game and leave them out of the
    # "deadline set" fan-out (they get the reply). A browser caller is the
    # Bearer user.
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None

class JoinGameRequest(BaseModel):
    """Body for ``POST /games/{game_id}/join``.

    ``game_id`` is **optional and redundant** -- the path is the single source of
    truth (G6). It used to be required, so omitting it was a 422 even though the
    value was right there in the URL, *and* supplying a different value than the
    path was accepted without complaint. Both are fixed: it may be omitted, and a
    value that disagrees with the path is a 400 rather than silently ignored.
    Kept in the model at all only because every existing caller sends it (the bot,
    the demo-game seeder, the web client, and ~40 tests); dropping the field
    outright would have made Pydantic reject them all.
    """
    telegram_id: Optional[str] = None  # Optional when using Bearer token (browser)
    bot_secret: Optional[str] = None
    game_id: Optional[int] = None  # redundant with the path; validated to agree if sent
    power: str
    join_password: Optional[str] = None  # W8: required for a private game

class QuitGameRequest(BaseModel):
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None
    power: Optional[str] = None  # Optional: if provided, must match user's power

class ReplacePlayerRequest(BaseModel):
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None
    power: str
    join_password: Optional[str] = None  # W8: required for a private game


class JoinPasswordRequest(BaseModel):
    """Body for ``POST /games/{game_id}/join_password`` (W8). Null opens the game."""
    join_password: Optional[str] = None
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


# W8: wrong-password guesses per user per game, as tight as the login limit.
_JOIN_PASSWORD_RATE_LIMIT_MAX = 5
_JOIN_PASSWORD_RATE_LIMIT_WINDOW = 900  # 15 minutes


def _checked_join_password(password: Optional[str]) -> Optional[str]:
    """The bcrypt hash for a new join password, or None to open the game."""
    if password is None:
        return None
    if not 4 <= len(password) <= 64:
        raise HTTPException(status_code=400, detail="A join password must be 4-64 characters.")
    return _hash_password(password)


def _require_join_password(game_id: str, user: Any, supplied: Optional[str]) -> None:
    """Refuse (403) to seat ``user`` in a private game without its password (W8).

    Open games and the game's creator pass. Failed guesses count against a
    per-user, per-game budget (429 once it's spent), like login attempts.
    """
    password_hash = game_service.join_password_hash(game_id)
    if password_hash is None:
        return
    creator = (game_service.meta(game_id) or {}).get("created_by_user_id")
    if creator is not None and int(creator) == int(user.id):
        return
    key = f"join_pw:{game_id}:{user.id}"
    _check_rate_limit(key, _JOIN_PASSWORD_RATE_LIMIT_MAX, _JOIN_PASSWORD_RATE_LIMIT_WINDOW)
    if supplied and _verify_password(supplied, password_hash):
        return
    _record_attempt(key)
    raise HTTPException(
        status_code=403,
        detail=(
            f"Game {game_id} is private: ask its creator for the join password."
            if not supplied
            else f"Wrong join password for game {game_id}."
        ),
    )

class MarkInactiveRequest(BaseModel):
    admin_token: str


class SpectateRequest(BaseModel):
    """Request for spectate endpoints (join/leave)."""
    telegram_id: Optional[str] = None  # Optional when using Bearer token (browser)
    bot_secret: Optional[str] = None


class DrawVoteRequest(BaseModel):
    """Request model for casting a draw vote for a power."""
    power: str
    vote: bool
    telegram_id: Optional[str] = None  # Optional when using Bearer token (browser)
    bot_secret: Optional[str] = None


class ProposeDeadlineRequest(BaseModel):
    """Request model for starting a majority vote on a new deadline."""
    power: str
    # Hours from now; omit (or null) to propose *clearing* the deadline.
    hours: Optional[float] = None
    # How long the vote itself stays open, in hours; omit for no expiry (it
    # then only resolves by majority or being withdrawn).
    vote_hours: Optional[float] = None
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


class DeadlineProposalVoteRequest(BaseModel):
    """Request model for voting yes/no on the pending deadline proposal."""
    power: str
    vote: bool
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


class WithdrawDeadlineProposalRequest(BaseModel):
    """Request model for the proposer withdrawing their pending deadline proposal."""
    power: str
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None


class ConcedeRequest(BaseModel):
    """Request model for a power conceding (voluntarily leaving) a game."""
    power: str
    telegram_id: Optional[str] = None  # Optional when using Bearer token (browser)
    bot_secret: Optional[str] = None

# --- Game Management Endpoints ---
REQUIRED_POWERS = {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}


@router.post("/games/create")
def create_game(
    req: CreateGameRequest,
    _: None = Depends(require_bot_or_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Create a new game. The new engine starts it immediately at S1901M with every
    power's opening units; players then claim powers via add_player/join.

    **Authentication is required, deliberately** (G6 decision, recorded
    2026-07-30). An unauthenticated game-creation endpoint is an obvious spam
    vector -- each call writes a `games` row with a full serialized `GameState` --
    and C2 added per-IP rate limiting for exactly that class of abuse. Requiring a
    Bearer token or `X-Bot-Secret` is the safe default for a public HTTP surface,
    and every real caller already has one.

    What actually made this feel like a wart was the *error*: an opaque 401
    "Not authenticated" with no hint that a header was missing. That is fixed in
    `require_bot_or_user`, which now names both accepted credentials.
    """
    if req.phase_length_seconds is not None and req.phase_length_seconds < 0:
        raise HTTPException(
            status_code=400,
            detail="phase_length_seconds must be >= 0 (0 means no automatic deadline)",
        )
    # The creator, when the caller is a person: a Bearer user, or the bot passing
    # telegram_id. A bare X-Bot-Secret (the demo seeder) creates an ownerless game.
    creator_id: Optional[int] = None
    if credentials is not None or req.telegram_id:
        creator = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        creator_id = int(creator.id)
    try:
        game_id = game_service.create_game(
            map_name=req.map_name,
            phase_length_seconds=req.phase_length_seconds,
            created_by_user_id=creator_id,
            dummy_powers=req.dummy_powers,
            auto_process=req.auto_process,
            join_password_hash=_checked_join_password(req.join_password),
        )
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"game_id": game_id}


@router.post("/games/{game_id}/join_password")
def set_join_password(
    game_id: str,
    req: JoinPasswordRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_admin_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Set, change, or (with ``null``) remove a game's join password (W8).

    Creator or admin only; a game with no recorded creator is admin-only.
    Players already seated are unaffected.
    """
    meta = game_service.meta(game_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if not is_admin_token(x_admin_token):
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        if meta.get("created_by_user_id") is None or int(user.id) != int(meta["created_by_user_id"]):
            raise HTTPException(status_code=403, detail="Only the game's creator can change its join password.")
    game_service.set_join_password_hash(game_id, _checked_join_password(req.join_password))
    invalidate_cache(f"games/{game_id}")
    return {"status": "ok", "private": req.join_password is not None}


@router.post("/games/{game_id}/auto_process")
def set_auto_process(
    game_id: str,
    req: AutoProcessRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_admin_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Switch W10's "process as soon as all orders are in" on or off.

    Any player in the game may (or an admin), like setting a deadline: everyone
    is told, and anyone who wants time can raise a wait flag
    (``POST .../wait``). Switching it on processes the turn at once if it is
    already complete.
    """
    game = db_service.get_game_by_game_id(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    caller_telegram_id = None
    if not is_admin_token(x_admin_token):
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        if db_service.get_player_by_game_id_and_user_id(game_id=int(game.id), user_id=int(user.id)) is None:
            raise HTTPException(status_code=403, detail="You are not a player in this game.")
        caller_telegram_id = getattr(user, "telegram_id", None)
    try:
        game_service.set_auto_process(game_id, req.enabled)
    except GameOverError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")
    notify_players(
        int(game.id),
        (
            f"Game {game_id} now processes each turn as soon as all orders are in. "
            f"Need more time? /notready {game_id}."
        )
        if req.enabled
        else f"Game {game_id} no longer processes turns automatically.",
        exclude_telegram_id=caller_telegram_id,
    )
    processed = api_shared.maybe_auto_process(game_id) if req.enabled else 0
    return {"status": "ok", "auto_process": req.enabled, "auto_processed": processed}


@router.post("/games/{game_id}/wait")
def set_wait_flag(
    game_id: str,
    req: WaitFlagRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Raise (``waiting: true``) or lower this power's wait flag (W10).

    A raised flag stops auto-processing for the current phase ("I'm still
    negotiating"); it is cleared when the turn is processed. It never stops a
    deadline, or a player pressing /processturn. Lowering the last flag
    processes the turn at once if everything else is ready.
    """
    _authorize_power(credentials, game_id, req.power, req.telegram_id, req.bot_secret)
    game = db_service.get_game_by_game_id(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    power = req.power.upper()
    try:
        waiting = game_service.set_wait(game_id, power, req.waiting)
    except GameOverError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")
    notify_players(
        int(game.id),
        f"{power} asks game {game_id} to wait before the turn is processed."
        if req.waiting
        else f"{power} is ready in game {game_id}.",
        exclude_telegram_id=_caller_telegram_id(credentials, req.telegram_id),
    )
    processed = 0 if req.waiting else api_shared.maybe_auto_process(game_id)
    return {"status": "ok", "waiting": waiting, "auto_processed": processed}


@router.post("/games/{game_id}/dummies")
def set_dummy_power(
    game_id: str,
    req: SetDummyRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_admin_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Leave ``power`` to civil disorder (``dummy: true``) or open it for a
    player again (``dummy: false``). W9.

    Only the game's creator, or an admin (``X-Admin-Token``), may change it; a
    game with no recorded creator (waiting-list games, older games) is
    admin-only. Only an empty seat can become a dummy.
    """
    meta = game_service.meta(game_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Game not found")
    if not is_admin_token(x_admin_token):
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        if meta.get("created_by_user_id") is None or int(user.id) != int(meta["created_by_user_id"]):
            raise HTTPException(status_code=403, detail="Only the game's creator can change its dummy powers.")
    try:
        dummies = game_service.set_dummy(game_id, req.power, req.dummy)
    except GameOverError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except OrderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")
    power = req.power.upper()
    if req.dummy:
        # The new dummy may have been the last power being waited on (W10).
        api_shared.maybe_auto_process(game_id)
    notify_players(
        int(game_id),
        f"{power} in game {game_id} is now played by civil disorder."
        if req.dummy
        else f"{power} in game {game_id} is open again -- /join {game_id} to take it.",
    )
    return {"status": "ok", "dummy_powers": dummies}


@router.post("/games/add_player")
def add_player(
    req: AddPlayerRequest,
    _: None = Depends(require_bot_or_user),
) -> Dict[str, Any]:
    """Assign a power in a game to a player (power->user, in the players table)."""
    row = db_service.get_game_by_game_id(str(req.game_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    power = req.power.upper()
    if power not in REQUIRED_POWERS:
        raise HTTPException(status_code=400, detail=f"Unknown power {req.power}")
    taken = {p.power_name for p in db_service.get_players_by_game_id(int(row.id))}
    if power in taken:
        raise HTTPException(status_code=400, detail=f"Power {power} already taken")
    player = db_service.create_player(int(row.id), power)
    return {"status": "ok", "player_id": getattr(player, "id", None)}


def _caller_telegram_id(
    credentials: Optional[HTTPAuthorizationCredentials],
    telegram_id: Optional[str],
) -> Optional[str]:
    """The caller's Telegram id, for skipping their own notification (G3a).

    A player who takes an action gets the outcome in their HTTP response, so
    DM'ing them the same news is noise -- the same reasoning as
    ``process_turn``'s ``exclude_telegram_id``.

    Two auth modes, two places to look: the bot passes ``telegram_id`` in the
    request body, while a browser caller is identified only by their Bearer
    token, so the id has to be read off the resolved user. Returns ``None`` when
    neither yields one, which simply means nobody is excluded.
    """
    if telegram_id:
        return str(telegram_id)
    user = get_current_user_optional(credentials)
    if user is not None and user.telegram_id:
        return str(user.telegram_id)
    return None


def _authorize_process_turn(
    game_id: str,
    credentials: Optional[HTTPAuthorizationCredentials],
    x_bot_secret: Optional[str],
    x_admin_token: Optional[str],
    telegram_id: Optional[str] = None,
) -> Optional[str]:
    """Only the game's creator may end its turn early -- plus the bot secret
    and admin-token holders, who are not players.

    Before this, any player seated in the game could (and, before E1d, any
    logged-in stranger): one player pressing "Process turn" turned every other
    player's unsent orders into holds. Turns end at the deadline or, with
    auto-process on, as soon as every order is in; ending one early is the
    creator's call. That applies to a web user (Bearer) and to a Telegram
    player (the bot passes their ``telegram_id``); the bot's demo game is
    created by its player, so it keeps working. A bare bot secret (scripts,
    the demo seeder) is trusted as before. A game nobody created (a
    waiting-list game) can be ended early only by an admin.

    Returns the authorizing player's ``telegram_id`` when the caller is a
    player, else ``None``. The route uses it to skip notifying whoever pressed
    the button -- they get the resolution in their HTTP response instead (G3).
    """
    creator = (game_service.meta(game_id) or {}).get("created_by_user_id")
    refused = HTTPException(
        status_code=403,
        detail=(
            "Only the game's creator can end a turn early. The turn is processed "
            "at the deadline, or as soon as every order is in if auto-process is on."
        ),
    )
    if is_bot_secret(x_bot_secret):
        if not telegram_id:
            return None
        player = db_service.get_user_by_telegram_id(str(telegram_id))
        if player is not None and creator is not None and int(player.id) == int(creator):
            return str(telegram_id)
        raise refused
    if is_admin_token(x_admin_token):
        return None
    user = get_current_user_optional(credentials)
    if user is None:
        raise HTTPException(status_code=403, detail="Not authorized to process this game's turn")
    if creator is None or int(user.id) != int(creator):
        raise refused
    # Direct attribute access, not getattr-with-default: `telegram_id` really is
    # a column on UserModel, and defaulting it to None is what hid this whole
    # bug class in notify_players.
    return str(user.telegram_id) if user.telegram_id else None


@router.post("/games/{game_id}/process_turn")
async def process_turn(
    game_id: str,
    require_all: bool = False,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_bot_secret: Optional[str] = Header(None),
    x_admin_token: Optional[str] = Header(None),
    body: Optional[Dict[str, Any]] = Body(None),
) -> Dict[str, Any]:
    """Adjudicate all pending orders and advance the phase.

    ``require_all=true`` refuses (400) unless every power that still controls at
    least one unit has submitted orders this phase; clients that want a hard gate
    on full submission pass it explicitly. Defaults to ``false`` (unchanged
    behaviour) -- the deadline scheduler never passes it, since a missed deadline
    must still process whatever was submitted.

    Only the game's creator (Bearer, or a Telegram player via the bot), the
    bot secret, or an admin-token holder may call this -- see
    ``_authorize_process_turn``. The deadline
    scheduler bypasses this entirely: it calls ``GameService.process_turn``
    directly (``api/shared.py``'s ``process_due_deadlines``), never over HTTP.

    The in-process ``asyncio.Lock`` below only protects against two concurrent
    calls *within this worker*; it does not survive a second uvicorn worker. The
    real cross-process guard is ``expected_phase_code`` in ``GameService.process_turn``
    -> ``GameRepo.save_state``, which raises ``StaleGameError`` (surfaced here as
    409) if another process already advanced the phase.
    """
    if not game_service.exists(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    caller_telegram_id = _authorize_process_turn(
        game_id, credentials, x_bot_secret, x_admin_token, (body or {}).get("telegram_id")
    )
    if require_all:
        status = game_service.orders_status(game_id)
        if status and status["missing"]:
            raise HTTPException(
                status_code=400,
                detail=f"Not all powers have submitted orders: missing {status['missing']}",
            )
    prev_view = game_service.view(game_id)
    prev_phase_code = prev_view["phase"] if prev_view else None
    lock = get_process_turn_lock(game_id)
    if lock.locked():
        raise HTTPException(status_code=409, detail="Turn processing already in progress for this game")
    async with lock:
        try:
            turn_result = game_service.process_turn(game_id)
        except (StaleGameError, GameOverError) as e:
            # Both are "the game is not where you think it is": another process
            # already advanced the phase, or the game has ended. Before the
            # GameOverError guard, processing a finished game "succeeded" with an
            # empty resolution and then DMed every player "turn processed".
            raise HTTPException(status_code=409, detail=str(e)) from e
    row = db_service.get_game_by_game_id(game_id)
    if row is not None:
        # Snapshot, cache, deadline, wait flags, DAIDE and the notification
        # fan-out -- shared with the deadline scheduler and W10's
        # auto-processing so the three triggers cannot drift apart. The caller
        # is left out of the DMs: the resolution is in their response below.
        api_shared.finish_processed_turn(
            game_id,
            int(row.id),
            prev_phase_code=prev_phase_code,
            trigger="manual",
            exclude_telegram_id=caller_telegram_id,
        )
    return {
        "status": "ok",
        "phase": turn_result["phase"],
        "game_status": turn_result["status"],
        "resolution": turn_result["resolution"],
    }


@router.post("/games/{game_id}/start")
def start_game(game_id: str) -> Dict[str, Any]:
    """No-op start: the new engine has no lobby/Pregame — a created game is already
    at S1901M. Kept for API compatibility; returns the current opening phase."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    invalidate_cache(f"games/{game_id}")
    return {"status": "ok", "phase": "Movement", "phase_code": view["phase"]}


@router.get("/games/{game_id}/state")
@cached_response(ttl=30, key_params=["game_id"])
def get_game_state(game_id: str) -> Dict[str, Any]:
    """Current game state in the new GameState-native shape (see GameService.view)."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return view

@router.get("/games/{game_id}/last_resolution")
def get_last_resolution(game_id: str) -> Dict[str, Any]:
    """The most recently adjudicated turn's per-order outcomes.

    A page reload loses whatever ``process_turn`` returned inline (see its
    ``resolution`` field); this is how a client re-fetches it afterwards.
    404 when the game doesn't exist; ``{"results": []}`` when it exists but no
    turn has been processed yet. See ``GameService.last_resolution_view`` for
    the payload shape -- the canonical ``engine.serialization.resolution_to_dict``
    fields (``order``, ``result``, ``dislodged``, ``retreat_options``) per entry,
    plus convenience ``power``/``order_str`` fields so a client can answer "what
    happened to my orders?" without re-deriving adjudication.
    """
    view = game_service.last_resolution_view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return view


@router.get("/games/{game_id}/orders_status")
def get_orders_status(game_id: str) -> Dict[str, Any]:
    """Which powers have submitted orders for the current phase, and which are
    still outstanding. Powers of eliminated/no-unit players are never "missing"
    (there is nothing for them to order). Used by ``require_all=true`` on
    ``process_turn`` and by the Telegram ``/status`` command."""
    status = game_service.orders_status(game_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return status

@router.post("/games/{game_id}/draw_vote")
def submit_draw_vote(
    game_id: str,
    req: DrawVoteRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Cast this power's yes/no draw vote for the current phase.

    Only the assigned user for ``power`` may vote it (same auth check as order
    submission). If this vote reaches quorum -- every non-eliminated power that
    still has a unit has now voted yes -- the game is finalized as a draw
    immediately; the response's ``quorum_reached``/``game_status`` reflect that.
    """
    _authorize_power(credentials, game_id, req.power, req.telegram_id, req.bot_secret)
    if not game_service.exists(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    try:
        result = game_service.submit_draw_vote(game_id, req.power, req.vote)
    except OrderError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (StaleGameError, GameOverError) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")

    # G3a: tell the other players. `submit_draw_vote` finalizes the game inline
    # the moment quorum is reached and returns the outcome only to the power that
    # cast the deciding vote -- and because the game is then COMPLETED, the
    # deadline scheduler skips it (`get_games_with_deadlines_and_active_status`),
    # so no later turn-processed fan-out covers for it. A game could end by
    # agreement and six of seven players find out by refreshing.
    #
    # Best-effort, like every other notification: a Telegram outage must not fail
    # a draw already committed to Postgres.
    try:
        row = db_service.get_game_by_game_id(game_id)
        if row is not None:
            if result.get("quorum_reached"):
                # A draw ends the game inline, without a turn being processed --
                # there will never be another one, so clear a stale deadline
                # rather than leave it displayed by /status.
                db_service.update_game_deadline(int(row.id), None)
                notify_turn_processed(
                    game_id,
                    int(row.id),
                    trigger="manual",
                    game_ended=True,
                    exclude_telegram_id=_caller_telegram_id(credentials, req.telegram_id),
                )
            elif req.vote:
                # A vote that does *not* end the game is still worth announcing:
                # otherwise a player only discovers a draw is being negotiated by
                # running /status, and a draw is the one outcome every power has a
                # veto over.
                # Both fields are always lists from `GameService.submit_draw_vote`:
                # `votes` is the yes-voters, `required` every power that must agree.
                votes = result.get("votes") or []
                required = result.get("required") or []
                notify_players(
                    int(row.id),
                    f"{req.power} has voted to end game {game_id} in a draw "
                    f"({len(votes)}/{len(required)} agreed). "
                    f"Use /draw to agree or /nodraw to withdraw.",
                    exclude_telegram_id=_caller_telegram_id(credentials, req.telegram_id),
                )
    except Exception as e:
        scheduler_logger.error(f"Failed to notify draw vote for game {game_id}: {e}")
    return result


@router.get("/games/{game_id}/draw_vote_status")
def draw_vote_status(game_id: str) -> Dict[str, Any]:
    """Who's voted yes to draw this phase, how many are needed, and whether
    quorum is reached. Read-only, no auth required (same as other status-read
    endpoints, e.g. ``/orders_status``)."""
    status = game_service.get_draw_votes(game_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return status


@router.post("/games/{game_id}/concede")
def concede_game(
    game_id: str,
    req: ConcedeRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """A single power voluntarily leaves the game. Only the assigned user for
    ``power`` may concede it. Unlike a draw vote, this does not end the game --
    the remaining powers play on; the conceding power's units are removed and
    it is picked up by the normal elimination check once it also holds no
    supply centers."""
    _authorize_power(credentials, game_id, req.power, req.telegram_id, req.bot_secret)
    if not game_service.exists(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    try:
        result = game_service.concede(game_id, req.power)
    except OrderError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except GameOverError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")

    # G3a: a power leaving changes the board for everyone -- its units come off
    # immediately -- and used to be invisible until somebody looked. Not a
    # turn-processed event (the game continues), so a plain `notify_players`
    # rather than the `notify_turn_processed` fan-out.
    try:
        row = db_service.get_game_by_game_id(game_id)
        if row is not None:
            notify_players(
                int(row.id),
                f"{req.power} has conceded and left game {game_id}. "
                f"Its units have been removed and its supply centres are now neutral; "
                f"the remaining powers play on.",
                exclude_telegram_id=_caller_telegram_id(credentials, req.telegram_id),
            )
    except Exception as e:
        scheduler_logger.error(f"Failed to notify concession for game {game_id}: {e}")
    return result


@router.get("/games")
def list_games() -> Dict[str, Any]:
    """List all games with basic info and player count."""
    try:
        games = db_service.get_all_games()
        result: list[dict[str, Any]] = []
        for g in games:
            players = db_service.get_players_by_game_id(int(g.id))  # type: ignore
            result.append({
                "id": g.id,
                "map_name": g.map_name,
                "game_id": getattr(g, 'game_id', None),
                "current_turn": getattr(g, 'current_turn', 0),
                "current_year": getattr(g, 'year', 1901),
                "current_season": getattr(g, 'season', "Spring"),
                "current_phase": getattr(g, 'current_phase', "Movement"),
                "status": getattr(g, 'status', "active"),
                "player_count": len(players),
                # Seats a human can hold: 7 minus the civil-disorder dummies (W9).
                "max_players": len(REQUIRED_POWERS) - len(g.dummy_powers or []),
                "dummy_powers": sorted(g.dummy_powers or []),
                "private": g.join_password_hash is not None,  # W8; never the hash
                "players": [{"power": p.power_name, "user_id": p.user_id} for p in players]
            })
        return {"games": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/players")
@cached_response(ttl=60, key_params=["game_id"])
def get_players(game_id: str) -> List[Dict[str, Any]]:
    """Get all players in a game."""
    try:
        game = db_service.get_game_by_game_id(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        players = db_service.get_players_by_game_id(int(game.id))  # type: ignore
        result = []
        for p in players:
            user = db_service.get_user_by_id(int(p.user_id)) if p.user_id else None  # type: ignore
            result.append({
                "power": p.power_name,
                "user_id": p.user_id,
                "is_active": getattr(p, 'is_active', True),
                "telegram_id": getattr(user, 'telegram_id', None) if user else None,
                "full_name": getattr(user, 'full_name', None) if user else None,
            })
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/spectate")
def spectate_join(
    game_id: str,
    req: SpectateRequest = Body(default_factory=SpectateRequest),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Join a game as spectator (non-player observer). Requires auth (Bearer or telegram_id)."""
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        db_service.add_spectator(game_id=game_id, user_id=int(user.id))
        return {"status": "ok", "message": f"Now spectating game {game_id}", "game_id": game_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error joining as spectator: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/games/{game_id}/spectate")
def spectate_leave(
    game_id: str,
    req: SpectateRequest = Body(default_factory=SpectateRequest),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Stop spectating a game."""
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        db_service.remove_spectator(game_id=game_id, user_id=int(user.id))
        return {"status": "ok", "message": f"Stopped spectating game {game_id}", "game_id": game_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error leaving spectate: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/spectators")
def get_spectators(game_id: str) -> Dict[str, Any]:
    """List spectators for a game."""
    try:
        spectators = db_service.get_spectators(game_id)
        return {"status": "ok", "game_id": game_id, "spectators": spectators}
    except Exception as e:
        logger.exception(f"Error listing spectators: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/games/{game_id}/observer_state")
@cached_response(ttl=30, key_params=["game_id"])
def get_observer_state(game_id: str) -> Dict[str, Any]:
    """
    Get game state for observers: same as /state but with orders hidden
    (pending orders, retreats, builds, destroys, order_history, adjudication_results).
    """
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    # Observers see the board but not submitted orders.
    view = dict(view)
    view["orders"] = {}
    return view


@router.post("/games/{game_id}/join")
def join_game(
    game_id: int,
    req: JoinGameRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    # The path is the single source of truth for which game this is. A body
    # `game_id` that disagrees with it is rejected rather than ignored: silently
    # accepting a mismatch was the one behaviour G6 ruled out, because it makes a
    # client bug look like a working request that joined the wrong game.
    if req.game_id is not None and int(req.game_id) != int(game_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"game_id in body ({req.game_id}) does not match the URL ({game_id}). "
                f"The body field is optional -- omit it and the path is used."
            ),
        )
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        # Validate power name
        valid_powers = {'ENGLAND', 'FRANCE', 'GERMANY', 'RUSSIA', 'TURKEY', 'AUSTRIA', 'ITALY'}
        if req.power.upper() not in valid_powers:
            raise HTTPException(status_code=400, detail=f"Invalid power name: {req.power}")
        view = game_service.view(str(game_id))
        if view is not None and view["status"] == "COMPLETED":
            raise HTTPException(status_code=409, detail=f"Game {game_id} has ended; it cannot be joined.")
        if view is not None and req.power.upper() in view.get("dummy_powers", []):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"{req.power.upper()} is played by civil disorder in game {game_id}; "
                    f"the game's creator can open it."
                ),
            )
        # Check if already joined
        existing = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if existing:
            return {"status": "already_joined", "player_id": existing.id}
        _require_join_password(str(game_id), user, req.join_password)
        # Check if power is taken. A seat row with no user is *vacant* (its
        # player quit, or an admin marked it inactive): joining it is the
        # ordinary way back in -- the web client lists such seats as "Open",
        # and /replace is the same operation under another name.
        taken = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        if taken is not None and taken.user_id is not None:
            raise HTTPException(status_code=409, detail="Power already taken")
        if taken is not None:
            db_service.assign_player_seat(int(taken.id), int(user.id), True)  # type: ignore
        else:
            # Assign the power to this user (players table only; state is engine-owned).
            db_service.create_player(game_id, req.power.upper(), user_id=int(user.id))  # type: ignore
        # Notification logic (only if user has telegram_id)
        telegram_id_val = getattr(user, "telegram_id", None)
        if telegram_id_val:
            notify_user(telegram_id_val, f"You have joined game {game_id} as {req.power}.", game_buttons(game_id))
        # Get player model for return value
        player_model = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        player_id = player_model.id if player_model else user.id
        try:
            game = db_service.get_game_by_id(int(game_id)) if isinstance(game_id, int) else db_service.get_game_by_game_id(str(game_id))  # type: ignore
            if game:
                notify_players(int(game.id), f"Player {user.full_name or telegram_id_val or 'Player'} has joined game {game_id} as {req.power}.")  # type: ignore
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players of join event: {e}")
        # Game start notification
        try:
            game = db_service.get_game_by_id(int(game_id)) if isinstance(game_id, int) else db_service.get_game_by_game_id(str(game_id))  # type: ignore
            if game is not None and hasattr(game, "map_name") and (game.map_name == "standard"):  # type: ignore
                required_powers = 7
            else:
                required_powers = 7
            player_count = len(db_service.get_players_by_game_id(int(game.id))) if game and game.id is not None else 0  # type: ignore
            # Dummies fill their seats too (W9): 5 humans + 2 dummies is a full game.
            player_count += len(view.get("dummy_powers", [])) if view is not None else 0
            if player_count >= required_powers:
                notify_players(int(game.id), f"Game {game_id} is now full. The game has started! Good luck to all players.", buttons=game_buttons(game_id))  # type: ignore
        except Exception as e:
            scheduler_logger.error(f"Failed to notify game start: {e}")
        invalidate_cache(f"games/{str(game_id)}")
        return {"status": "ok", "player_id": player_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/quit")
def quit_game(
    game_id: int,
    req: QuitGameRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        # If power is specified, check that user owns that power
        if req.power:
            player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
            if player is None:
                raise HTTPException(status_code=404, detail="Power not found in game")
            if player.user_id is None or int(player.user_id) != int(user.id):  # type: ignore
                raise HTTPException(status_code=403, detail="You are not authorized to quit this power.")
        else:
            # If no power specified, find player by user_id
            player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
            if player is None:
                raise HTTPException(status_code=404, detail="Player not found in game")
        # Vacate the seat: user_id -> NULL, is_active -> False, one commit.
        db_service.assign_player_seat(int(player.id), None, False)
        telegram_id_val = getattr(user, "telegram_id", None)
        if telegram_id_val:
            invalidate_cache(f"users/{telegram_id_val}")
        invalidate_cache(f"games/{game_id}")  # the cached /players list must not show them
        # Notification logic (only if user has telegram_id)
        telegram_id_val = getattr(user, "telegram_id", None)
        if telegram_id_val:
            notify_user(telegram_id_val, f"You have quit game {game_id}.")
        try:
            power_name = getattr(player, "power_name", None) or getattr(player, "power", None)
            notify_players(game_id, f"Player {user.full_name or getattr(user, 'telegram_id', None) or 'Player'} has left game {game_id} (power {power_name}).")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players of quit event: {e}")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/replace")
def replace_player(
    game_id: int,
    req: ReplacePlayerRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Replace a vacated power in a game."""
    try:
        user = resolve_user_or_telegram(credentials, req.telegram_id, bot_secret=req.bot_secret)
        # Find the player slot for this power
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        if player is None:
            raise HTTPException(status_code=404, detail="Power not found in game")
        # Only allow replacement if user_id is None and is_active is False
        if player.user_id is not None:
            raise HTTPException(status_code=400, detail="Power is already assigned to a user. Only unassigned, inactive powers can be replaced.")
        if getattr(player, 'is_active', True) is True:
            raise HTTPException(status_code=400, detail="Power is not inactive and cannot be replaced. Only inactive/vacated powers can be replaced.")
        # Check if user is already in the game
        already_in_game = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if already_in_game:
            raise HTTPException(status_code=400, detail="User is already in the game")
        _require_join_password(str(game_id), user, req.join_password)
        # Fill the seat: user_id -> user, is_active -> True, one commit.
        db_service.assign_player_seat(int(player.id), int(user.id), True)  # type: ignore
        telegram_id_val = getattr(user, "telegram_id", None)
        if telegram_id_val:
            invalidate_cache(f"users/{telegram_id_val}")
        invalidate_cache(f"games/{game_id}")
        try:
            notify_players(
                game_id,
                f"{user.full_name or telegram_id_val or 'A new player'} has taken over "
                f"{req.power.upper()} in game {game_id}.",
                exclude_telegram_id=telegram_id_val,
            )
        except Exception as e:
            scheduler_logger.error(f"Failed to notify replacement for game {game_id}: {e}")
        return {"status": "ok", "message": "Player replaced successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/players/{power}/mark_inactive")
def mark_player_inactive(game_id: int, power: str, req: MarkInactiveRequest) -> Dict[str, Any]:
    """Admin endpoint to mark a player as inactive (for replacement)."""
    if not is_admin_token(req.admin_token):
        raise HTTPException(status_code=403, detail="Invalid admin token")
    try:
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        if getattr(player, 'is_active', True) is False and player.user_id is None:
            return {"status": "already_inactive"}
        db_service.assign_player_seat(int(player.id), None, False)
        invalidate_cache(f"games/{game_id}")
        notify_players(game_id, f"Player {power} has been marked inactive by admin and is eligible for replacement.")
        return {"status": "ok", "game_id": game_id, "power": power}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _refuse_deadline_change_if_over(game: Any) -> None:
    """A finished game takes no writes (Track L); a deadline or a vote on one
    would only send players "deadline set" news about a game that is over."""
    if getattr(game, "status", None) == "completed":
        raise HTTPException(status_code=409, detail="Game is over; its deadline can no longer be changed.")


def _deadline_text(iso_value: Optional[str]) -> str:
    return api_shared.format_deadline_utc(datetime.fromisoformat(iso_value) if iso_value else None)


@router.get("/games/{game_id}/deadline")
def get_deadline(game_id: str) -> Dict[str, Any]:
    """Get the current deadline for a game, and any pending majority-vote
    proposal to change it (see ``POST .../deadline/propose``)."""
    try:
        game = db_service.get_game_by_game_id(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        deadline_value = getattr(game, 'deadline', None)
        proposal = db_service.get_pending_deadline_proposal(game_id)
        pending_proposal = None
        if proposal is not None:
            active = game_service.active_powers(game_id) or frozenset()
            pending_proposal = api_shared.deadline_proposal_view(proposal, active)
        return {
            "status": "ok",
            "deadline": deadline_value.isoformat() if deadline_value else None,
            # The recurring length a caller can arm a deadline from via this
            # route's POST; None means the default, 0 means none was set.
            "phase_length_seconds": getattr(game, "phase_length_seconds", None),
            "pending_proposal": pending_proposal,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/games/{game_id}/deadline/propose")
def propose_deadline(
    game_id: str,
    req: ProposeDeadlineRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Start a majority vote to change (``hours``) or clear (omit ``hours``)
    the deadline. Only the assigned user for ``power`` may propose for it.

    Resolves on the spot if the proposer alone is already a majority
    (single-active-power edge case); otherwise stays pending until
    ``POST .../deadline/vote`` reaches one, its own ``vote_hours`` expires, or
    the proposer withdraws it via ``POST .../deadline/withdraw``.
    """
    _authorize_power(credentials, game_id, req.power, req.telegram_id, req.bot_secret)
    game = db_service.get_game_by_game_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    _refuse_deadline_change_if_over(game)
    try:
        result = api_shared.propose_deadline(
            game_id, int(game.id), req.power, req.hours, req.vote_hours
        )
    except api_shared.DeadlineProposalError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")
    try:
        if result["status"] == "accepted":
            notify_players(
                int(game.id),
                f"{req.power}'s deadline proposal for game {game_id} was accepted "
                f"immediately (they're the only active power): deadline now "
                f"{_deadline_text(result['deadline'])}.",
                exclude_telegram_id=_caller_telegram_id(credentials, req.telegram_id),
            )
        else:
            needed = result["needed_for_majority"]
            what = f"{req.hours}h" if req.hours is not None else "clearing it"
            notify_players(
                int(game.id),
                f"{req.power} proposes changing game {game_id}'s deadline to {what}. "
                f"Needs {needed} yes votes ({len(result['yes_votes'])}/{needed} so far). "
                f"Use /deadline {game_id} vote yes|no.",
                exclude_telegram_id=_caller_telegram_id(credentials, req.telegram_id),
            )
    except Exception as e:
        scheduler_logger.error(f"Failed to notify deadline proposal for game {game_id}: {e}")
    return result


@router.post("/games/{game_id}/deadline/vote")
def vote_deadline_proposal(
    game_id: str,
    req: DeadlineProposalVoteRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Cast (or change) this power's yes/no vote on the pending deadline
    proposal. Only the assigned user for ``power`` may vote it."""
    _authorize_power(credentials, game_id, req.power, req.telegram_id, req.bot_secret)
    game = db_service.get_game_by_game_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    _refuse_deadline_change_if_over(game)
    try:
        result = api_shared.vote_on_deadline_proposal(game_id, int(game.id), req.power, req.vote)
    except api_shared.DeadlineProposalError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")
    try:
        exclude = _caller_telegram_id(credentials, req.telegram_id)
        if result["status"] == "accepted":
            notify_players(
                int(game.id),
                f"Game {game_id}'s deadline proposal passed: deadline now "
                f"{_deadline_text(result['deadline'])}.",
                exclude_telegram_id=exclude,
            )
        elif result["status"] == "rejected":
            notify_players(
                int(game.id),
                f"Game {game_id}'s deadline proposal (from {result['proposed_by']}) "
                f"was voted down; nothing changed.",
                exclude_telegram_id=exclude,
            )
        elif req.vote:
            needed = result["needed_for_majority"]
            notify_players(
                int(game.id),
                f"{req.power} voted yes on game {game_id}'s deadline proposal "
                f"({len(result['yes_votes'])}/{needed} needed).",
                exclude_telegram_id=exclude,
            )
    except Exception as e:
        scheduler_logger.error(f"Failed to notify deadline vote for game {game_id}: {e}")
    return result


@router.post("/games/{game_id}/deadline/withdraw")
def withdraw_deadline_proposal(
    game_id: str,
    req: WithdrawDeadlineProposalRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Dict[str, Any]:
    """Cancel the pending deadline proposal. Only its original proposer may."""
    _authorize_power(credentials, game_id, req.power, req.telegram_id, req.bot_secret)
    if not db_service.get_game_by_game_id(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    try:
        result = api_shared.withdraw_deadline_proposal(game_id, req.power)
    except api_shared.DeadlineProposalError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")
    return result

@router.post("/games/{game_id}/deadline")
def set_deadline(
    game_id: str,
    req: SetDeadlineRequest,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_bot_secret: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Set the deadline for a game.

    Uses ``update_game_deadline`` (opens and commits its own session), not a bare
    attribute assignment on the row returned by ``get_game_by_game_id`` -- that row
    is detached the moment its session-scoped ``with`` block exits, so mutating it
    afterwards is silently discarded (``DatabaseService.commit()`` is a documented
    no-op, not a real flush).
    """
    game = db_service.get_game_by_game_id(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    # Whoever the caller is -- Bearer user, or telegram_id + bot_secret -- they
    # must hold a power in this game. Until v2.7.79 (Track T) a Bearer caller
    # could omit telegram_id and set any game's deadline unchecked.
    user = resolve_user_or_telegram(
        credentials, req.telegram_id, bot_secret=req.bot_secret or x_bot_secret
    )
    member = db_service.get_player_by_game_id_and_user_id(game_id=int(game.id), user_id=int(user.id))
    if member is None:
        raise HTTPException(status_code=403, detail="You are not a player in this game.")
    _refuse_deadline_change_if_over(game)
    if req.phase_length_seconds is not None and req.phase_length_seconds < 0:
        raise HTTPException(
            status_code=400,
            detail="phase_length_seconds must be >= 0 (0 means no automatic deadline)",
        )
    try:
        if req.phase_length_seconds is not None:
            db_service.update_game_phase_length(int(game.id), req.phase_length_seconds)
        # A bare phase-length change with no explicit deadline arms one from the
        # new length immediately, so "make this game 10-minute phases" takes
        # effect now rather than waiting for someone to also pass a deadline.
        deadline = req.deadline
        if deadline is None and req.phase_length_seconds is not None:
            deadline = api_shared.next_deadline(req.phase_length_seconds)
        db_service.update_game_deadline(int(game.id), deadline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    # A new deadline gets its own 10-minute reminder, even if the previous one
    # for this phase already fired (extending a deadline after the reminder).
    api_shared.reminder_sent[int(game.id)] = False
    invalidate_cache(f"games/{game_id}")

    # Everyone plays to the same clock, so everyone hears it change. Best-effort,
    # like every other notification; the write above is already committed.
    try:
        if deadline is not None:
            when = api_shared.format_deadline_utc(deadline)
            text = (
                f"Deadline for game {game_id} set to {when}. Orders in by then; the turn "
                f"is processed automatically when it passes."
            )
        else:
            text = f"The deadline for game {game_id} has been removed; the turn will be processed by hand."
        notify_players(int(game.id), text, exclude_telegram_id=getattr(user, "telegram_id", None))
    except Exception as e:
        scheduler_logger.error(f"Failed to notify deadline change for game {game_id}: {e}")
    return {
        "status": "ok",
        "deadline": deadline.isoformat() if deadline else None,
        "phase_length_seconds": (
            req.phase_length_seconds
            if req.phase_length_seconds is not None
            else getattr(game, "phase_length_seconds", None)
        ),
    }

@router.get("/games/{game_id}/history/{turn}")
def get_game_history(game_id: str, turn: int) -> Dict[str, Any]:
    """Everything known about one past turn: the board it resulted in, the orders
    submitted to get there, and what those orders did.

    **Turn numbering.** ``turn`` T means: the snapshot written when T *began*
    (i.e. the board immediately after T-1 was adjudicated), plus
    ``order_history[T-1]`` and ``resolution_history[T-1]`` -- the orders given
    during T-1 and their outcomes, which is what produced this board.
    ``GameRepo.save_state`` keys a turn's history entry by the phase counter
    *before* it increments, but records the following snapshot *after* -- so a
    snapshot at T and its own history entry are one apart, not the same key.
    Turn 0's board has no snapshot (nothing has been processed yet); it is the
    standard opening position, and ``state`` is null for it.

    **This endpoint returned 500 for its entire existence before this fix.** It
    read ``snapshot.phase`` and ``snapshot.state``, neither of which is a column
    on ``MapSnapshotModel`` (they are ``phase_code`` and ``state_json``), so
    every call raised ``AttributeError`` into the blanket handler below and came
    back as "500 Internal Server Error". The ``resolution`` field is new: before
    this only the *latest* turn's outcomes were kept anywhere.
    """
    row = db_service.get_game_by_game_id(str(game_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    snapshot = db_service.get_game_snapshot_by_game_id_and_turn(game_id=int(row.id), turn=turn)
    orders = game_service.order_history(str(game_id)).get(str(turn - 1))
    resolution = game_service.resolution_history(str(game_id)).get(str(turn - 1))
    if snapshot is None and orders is None and resolution is None:
        raise HTTPException(status_code=404, detail="Nothing recorded for this turn.")
    return {
        "game_id": str(game_id),
        "turn": turn,
        "phase_code": snapshot.phase_code if snapshot is not None else None,
        "state": snapshot.state_json if snapshot is not None else None,
        "units": snapshot.units if snapshot is not None else None,
        "supply_centers": snapshot.supply_centers if snapshot is not None else None,
        "orders": orders,
        "resolution": resolution,
    }


@router.get("/games/{game_id}/resolutions")
def get_resolution_history(game_id: str) -> Dict[str, Any]:
    """Per-turn adjudication outcomes, ``{turn: resolution}`` -- the outcome half of
    ``GET /games/{id}/orders/history``.

    ``GET /games/{id}/last_resolution`` answers "what happened last turn" and is
    overwritten every turn; this answers it for every turn the game has played.
    Empty for turns processed before ``resolution_history`` existed.
    """
    if not game_service.exists(str(game_id)):
        raise HTTPException(status_code=404, detail="Game not found")
    return {"game_id": str(game_id), "resolutions": game_service.resolution_history(str(game_id))}

@router.post("/games/{game_id}/snapshot")
def save_game_snapshot(game_id: str, _: None = Depends(require_bot_or_user)) -> Dict[str, Any]:
    """Save a snapshot of the current game state. Any authenticated caller."""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    row = db_service.get_game_by_game_id(game_id)
    try:
        turn = int(getattr(row, "current_turn", 0) or 0)
        snapshot = db_service.create_game_snapshot(
            game_id=int(row.id),
            turn=turn,
            year=view["year"],
            season=view["season"],
            phase=view["phase_type"],
            phase_code=view["phase"],
            game_state=view,
            state_json=game_service.state_json(game_id),
        )
        return {"status": "ok", "snapshot_id": snapshot.id, "turn": turn}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/snapshots")
def get_game_snapshots(game_id: str) -> Dict[str, Any]:
    """Get all snapshots for a game"""
    try:
        game = db_service.get_game_by_game_id(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        snapshots = db_service.get_game_snapshots_by_game_id(int(game.id))  # type: ignore
        # Only the columns `MapSnapshotModel` actually has. This used to read
        # `snap.year`, `snap.season` and `snap.phase`, none of which exist on the
        # model, so the route raised AttributeError into the handler below and
        # returned 500 every time it was called. The year/season are recoverable
        # from `phase_code` ("S1901M") by any client that wants them.
        result = [
            {
                "id": snap.id,
                "turn": snap.turn_number,
                "phase_code": snap.phase_code,
                "created_at": snap.created_at.isoformat() if snap.created_at else None,
            }
            for snap in snapshots
        ]
        return {"status": "ok", "snapshots": result}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/restore/{snapshot_id}")
def restore_game_snapshot(
    game_id: str,
    snapshot_id: int,
    x_admin_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Restore a game's live state to a previous snapshot. **Admin only.**

    Rewinding a game discards every player's position since the snapshot, so it
    is gated on ``X-Admin-Token`` like the other moderation actions -- until
    ``v2.7.77`` (Track R) this route took no credentials at all, and nginx
    proxies ``/api/`` to the public internet. The players are told afterwards.

    Only snapshots taken after PR5 carry ``state_json`` (the raw serialized
    ``GameState``, the only shape ``state_from_dict`` can rebuild a ``Game`` from).
    Restoring an older, pre-PR5 snapshot -- which only has the view-shaped
    ``units``/``supply_centers`` -- now fails loudly with 409 instead of the old
    stub's silent no-op.
    """
    if not is_admin_token(x_admin_token):
        raise HTTPException(status_code=403, detail="Admin token required to restore a snapshot")
    row = db_service.get_game_by_game_id(game_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    snapshot = db_service.get_game_snapshot_by_id(snapshot_id, int(row.id))
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    snapshot_state_json = getattr(snapshot, "state_json", None)
    if not snapshot_state_json:
        raise HTTPException(
            status_code=409,
            detail="Snapshot predates state_json capture and cannot be restored",
        )
    try:
        game_service.restore_snapshot(game_id, snapshot_state_json, snapshot.phase_code)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Corrupt snapshot: {e}") from e
    invalidate_cache(f"games/{game_id}")
    try:
        notify_players(
            int(row.id),
            f"Game {game_id} has been rolled back by an admin to phase {snapshot.phase_code}. "
            f"Pending orders and draw votes were cleared -- check the board and submit fresh orders.",
        )
    except Exception as e:
        scheduler_logger.error(f"Failed to notify restore for game {game_id}: {e}")
    return {"status": "ok", "snapshot_id": snapshot_id, "phase_code": snapshot.phase_code}

@router.get("/games/{game_id}/debug/unit_locations")
def debug_unit_locations(game_id: str) -> Dict[str, Any]:
    """Get all unit locations in text format for debugging"""
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    unit_locations: Dict[str, List[str]] = {}
    for power, units in view["units_by_power"].items():
        unit_locations[power] = [f"{u['kind']} {u['location']}" for u in units]
    return {
        "status": "ok",
        "game_id": game_id,
        "phase": view["phase"],
        "unit_locations": unit_locations,
    }


@router.get("/games/{game_id}/legal_orders/{power}")
def get_legal_orders_for_power(game_id: str, power: str) -> Dict[str, Any]:
    """Phase-aware legal order strings for every unit ``power`` controls.

    Primary legal-orders endpoint. Delegates to the pure
    ``server.legal_orders.legal_orders_for_power`` (map + state -> data), which
    enumerates movement orders in a movement phase, retreat/disband orders in
    a retreat phase (from the dislodged unit's precomputed legal retreats),
    and build/waive or disband orders in an adjustment phase.
    """
    game = game_service.load(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return legal_orders_for_power(game_service.map, game.state, power.upper())


@router.get("/games/{game_id}/legal_orders/{power}/{unit}")
def get_legal_orders(game_id: str, power: str, unit: str) -> Dict[str, Any]:
    """Legal order strings for one unit: a lookup into the power-level route.

    Kept for backward compatibility with existing clients; the power-level
    route above is primary — ``%2F`` in a coast-bearing unit string like
    ``F STP/SC`` is awkward as a path segment, so new clients should prefer
    it. Behaviour preserved: 404 for an unknown game, 400 for a malformed
    unit string. A unit that exists but belongs to another power, or doesn't
    exist at all (or has no legal orders this phase), returns ``{"orders": []}``
    with 200 — never a 404, which would trip the frontend's fallback path.
    Accepts both ``"A PAR"`` and ``"F STP/SC"``; a bare ``"F STP"`` for a unit
    actually standing on a named coast falls back to a province-only match.
    """
    game = game_service.load(game_id)
    if game is None:
        raise HTTPException(status_code=404, detail="Game not found")
    parts = unit.upper().strip().split()
    if len(parts) < 2 or parts[0] not in ("A", "F"):
        raise HTTPException(status_code=400, detail=f"Invalid unit format: '{unit}'")
    kind, loc_token = parts[0], parts[1]
    province = loc_token.split("/")[0]

    data = legal_orders_for_power(game_service.map, game.state, power.upper())
    orders_by_unit: Dict[str, List[str]] = data["orders_by_unit"]

    exact_key = f"{kind} {loc_token}"
    if exact_key in orders_by_unit:
        return {"orders": orders_by_unit[exact_key]}

    # Fall back to a province-only match (e.g. "F STP" for a unit that
    # actually stands on a named coast, "F STP/SC").
    prefix = f"{kind} {province}"
    for key, orders in orders_by_unit.items():
        if key == prefix or key.startswith(prefix + "/"):
            return {"orders": orders}

    return {"orders": []}
