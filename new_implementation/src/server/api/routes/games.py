"""
Game management API routes.

This module contains all endpoints related to game creation, state management,
player management (join/quit/replace), deadlines, snapshots, and history.
"""
from fastapi import APIRouter, HTTPException, Body, Depends, Header
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

import requests
from fastapi.security import HTTPAuthorizationCredentials
from .auth import require_bot_or_user, resolve_user_or_telegram, get_current_user_optional, http_bearer
from .orders import _authorize_power
from .. import shared as api_shared
from ..shared import (
    db_service, game_service, logger, scheduler_logger, NOTIFY_URL, ADMIN_TOKEN, BOT_SECRET,
    notify_players, notify_turn_processed, get_process_turn_lock,
)
from ...legal_orders import legal_orders_for_power
from ...response_cache import cached_response, invalidate_cache
from persistence.game_repo import StaleGameError
from server.game_service import OrderError

router = APIRouter()

# --- Request Models ---
class CreateGameRequest(BaseModel):
    """Request model for creating a new game."""
    map_name: str = "standard"
    initial_phase: Optional[str] = None  # None or "Pregame" = lobby; "Movement" = start immediately (e.g. tests)

class AddPlayerRequest(BaseModel):
    """Request model for adding a player to a game."""
    game_id: str
    power: str

class SetDeadlineRequest(BaseModel):
    deadline: Optional[datetime]

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

class QuitGameRequest(BaseModel):
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None
    power: Optional[str] = None  # Optional: if provided, must match user's power

class ReplacePlayerRequest(BaseModel):
    telegram_id: Optional[str] = None
    bot_secret: Optional[str] = None
    power: str

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
    try:
        game_id = game_service.create_game(map_name=req.map_name)
        return {"game_id": game_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
) -> Optional[str]:
    """Only the bot-secret path, an admin-token holder, or a user who holds a
    power in this game may end this game's turn early.

    ``require_bot_or_user`` alone only checks that the caller is *someone*
    authenticated, not that they're *in this game* -- combined with
    ``require_all`` defaulting to ``false``, that let any logged-in stranger
    browsing "All games" end a turn early for all seven powers, converting
    everyone's unsubmitted units into holds. Everyone who fails all three
    checks below gets 403.

    Returns the authorizing player's ``telegram_id`` when the caller is a user
    who holds a power here, else ``None`` (bot-secret and admin-token callers are
    not players). The route uses it to skip notifying whoever pressed the button
    -- they get the resolution in their HTTP response instead (G3).
    """
    if x_bot_secret and BOT_SECRET and x_bot_secret == BOT_SECRET:
        return None
    if x_admin_token and x_admin_token == ADMIN_TOKEN:
        return None
    user = get_current_user_optional(credentials)
    if user is not None:
        row = db_service.get_game_by_game_id(game_id)
        if row is not None:
            player = db_service.get_player_by_game_id_and_user_id(
                game_id=int(row.id), user_id=int(user.id)
            )
            if player is not None:
                # Direct attribute access, not getattr-with-default: `telegram_id`
                # really is a column on UserModel, and defaulting it to None is
                # what hid this whole bug class in notify_players.
                return str(user.telegram_id) if user.telegram_id else None
    raise HTTPException(status_code=403, detail="Not authorized to process this game's turn")


@router.post("/games/{game_id}/process_turn")
async def process_turn(
    game_id: str,
    require_all: bool = False,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    x_bot_secret: Optional[str] = Header(None),
    x_admin_token: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """Adjudicate all pending orders and advance the phase.

    ``require_all=true`` refuses (400) unless every power that still controls at
    least one unit has submitted orders this phase; clients that want a hard gate
    on full submission pass it explicitly. Defaults to ``false`` (unchanged
    behaviour) -- the deadline scheduler never passes it, since a missed deadline
    must still process whatever was submitted.

    Only the bot-secret path (``X-Bot-Secret``), an admin-token holder
    (``X-Admin-Token``), or a Bearer-authenticated user who holds a power in
    this game may call this -- see ``_authorize_process_turn``. The deadline
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
    caller_telegram_id = _authorize_process_turn(game_id, credentials, x_bot_secret, x_admin_token)
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
        except StaleGameError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
    invalidate_cache(f"games/{game_id}")

    if api_shared.daide_server is not None:
        try:
            await api_shared.daide_server.notify_game_processed(game_id, resolved_phase=prev_phase_code)
        except Exception as e:
            logger.error(f"DAIDE notify_game_processed failed for {game_id}: {e}")

    try:
        row = db_service.get_game_by_game_id(game_id)
        view = game_service.view(game_id)
        if row is not None and view is not None:
            try:
                db_service.create_game_snapshot(
                    game_id=int(row.id),
                    turn=int(getattr(row, "current_turn", 0) or 0),
                    year=view["year"],
                    season=view["season"],
                    phase=view["phase_type"],
                    phase_code=view["phase"],
                    game_state=view,
                    state_json=game_service.state_json(game_id),
                )
            except Exception as e:
                logger.debug(f"process_turn: snapshot failed: {e}")
            game_ended = view["status"] == "COMPLETED"
            if not game_ended:
                db_service.update_game_deadline(int(row.id), datetime.now(timezone.utc) + timedelta(hours=24))
            else:
                db_service.update_game_deadline(int(row.id), None)
            # Before G3 this branch notified *only* on game end, so the ordinary
            # case -- everyone submitted, one player pressed the button -- told the
            # other six players nothing and posted nothing to the linked channel.
            # Same fan-out as the deadline path now; the caller is skipped because
            # the resolution is already in their response below.
            notify_turn_processed(
                game_id,
                int(row.id),
                trigger="manual",
                game_ended=game_ended,
                exclude_telegram_id=caller_telegram_id,
            )
    except Exception as e:
        scheduler_logger.error(f"process_turn post-processing error: {e}")
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
    except StaleGameError as e:
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
                f"Its units have been removed; the remaining powers play on.",
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
        # Check if already joined
        existing = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if existing:
            return {"status": "already_joined", "player_id": existing.id}
        # Check if power is taken
        taken = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        if taken:
            raise HTTPException(status_code=409, detail="Power already taken")
        # Assign the power to this user (players table only; state is engine-owned).
        db_service.create_player(game_id, req.power.upper(), user_id=int(user.id))  # type: ignore
        # Notification logic (only if user has telegram_id)
        telegram_id_val = getattr(user, "telegram_id", None)
        try:
            if telegram_id_val:
                try:
                    telegram_id_int = int(telegram_id_val)
                    requests.post(
                        NOTIFY_URL,
                        json={"telegram_id": telegram_id_int, "message": f"You have joined game {game_id} as {req.power}."},
                        timeout=2,
                    )
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify joining player: {e}")
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
            if player_count >= required_powers:
                notify_players(int(game.id), f"Game {game_id} is now full. The game has started! Good luck to all players.")  # type: ignore
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
            if int(player.user_id) != int(user.id):  # type: ignore
                raise HTTPException(status_code=403, detail="You are not authorized to quit this power.")
        else:
            # If no power specified, find player by user_id
            player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
            if player is None:
                raise HTTPException(status_code=404, detail="Player not found in game")
        # Unassign the user from the player slot
        try:
            db_service.delete_orders_by_player_id(int(player.id))  # type: ignore
            player.user_id = None  # type: ignore
            setattr(player, 'is_active', False)  # type: ignore
            db_service.update_player_is_active(int(player.id), False)  # type: ignore
            db_service.commit()
            telegram_id_val = getattr(user, "telegram_id", None)
            if telegram_id_val:
                invalidate_cache(f"users/{telegram_id_val}")
        except Exception:
            pass
        # Notification logic (only if user has telegram_id)
        try:
            telegram_id_val = getattr(user, "telegram_id", None)
            if telegram_id_val:
                try:
                    telegram_id_int = int(telegram_id_val)
                    requests.post(
                        NOTIFY_URL,
                        json={"telegram_id": telegram_id_int, "message": f"You have quit game {game_id}."},
                        timeout=2,
                    )
                except (ValueError, TypeError):
                    pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify quitting player: {e}")
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
        # Assign user to the player slot
        player.user_id = user.id  # type: ignore
        setattr(player, 'is_active', True)  # type: ignore
        db_service.update_player_is_active(int(player.id), True)  # type: ignore
        db_service.commit()
        db_service.refresh(player)
        return {"status": "ok", "message": "Player replaced successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/players/{power}/mark_inactive")
def mark_player_inactive(game_id: int, power: str, req: MarkInactiveRequest) -> Dict[str, Any]:
    """Admin endpoint to mark a player as inactive (for replacement)."""
    if req.admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")
    try:
        from persistence.database import PlayerModel
        player = db_service.get_player_by_game_id_and_power(game_id=game_id, power=power)
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        if getattr(player, 'is_active', True) is False and player.user_id is None:
            return {"status": "already_inactive"}
        with db_service.session_factory() as session:
            player_to_update = session.query(PlayerModel).filter_by(id=player.id).first()
            if player_to_update:
                player_to_update.user_id = None  # type: ignore
                player_to_update.is_active = False  # type: ignore
                session.commit()
                session.refresh(player_to_update)
        notify_players(game_id, f"Player {power} has been marked inactive by admin and is eligible for replacement.")
        return {"status": "ok", "game_id": game_id, "power": power}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/deadline")
def get_deadline(game_id: str) -> dict[str, Optional[str]]:
    """Get the current deadline for a game."""
    try:
        game = db_service.get_game_by_game_id(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        deadline_value = getattr(game, 'deadline', None)
        return {"status": "ok", "deadline": deadline_value.isoformat() if deadline_value else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/deadline")
def set_deadline(
    game_id: str,
    req: SetDeadlineRequest,
    _: None = Depends(require_bot_or_user),
) -> dict[str, Optional[str]]:
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
    try:
        db_service.update_game_deadline(int(game.id), req.deadline)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "ok", "deadline": req.deadline.isoformat() if req.deadline else None}

@router.get("/games/{game_id}/history/{turn}")
def get_game_history(game_id: int, turn: int) -> Dict[str, Any]:
    """Get the game state snapshot for a specific turn."""
    try:
        snapshot = db_service.get_game_snapshot_by_game_id_and_turn(game_id=game_id, turn=turn)
        if not snapshot:
            raise HTTPException(status_code=404, detail="No game state found for this turn.")
        return {"game_id": game_id, "turn": turn, "phase": snapshot.phase, "state": snapshot.state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/snapshot")
def save_game_snapshot(game_id: str) -> Dict[str, Any]:
    """Save a snapshot of the current game state"""
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
        result = []
        for snap in snapshots:
            result.append({
                "id": snap.id,
                "turn": snap.turn_number,
                "year": snap.year,
                "season": snap.season,
                "phase": snap.phase,
                "phase_code": snap.phase_code,
                "created_at": snap.created_at.isoformat() if hasattr(snap, 'created_at') and snap.created_at else None
            })
        return {"status": "ok", "snapshots": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/restore/{snapshot_id}")
def restore_game_snapshot(game_id: str, snapshot_id: int) -> Dict[str, Any]:
    """Restore a game's live state to a previous snapshot.

    Only snapshots taken after PR5 carry ``state_json`` (the raw serialized
    ``GameState``, the only shape ``state_from_dict`` can rebuild a ``Game`` from).
    Restoring an older, pre-PR5 snapshot -- which only has the view-shaped
    ``units``/``supply_centers`` -- now fails loudly with 409 instead of the old
    stub's silent no-op.
    """
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
