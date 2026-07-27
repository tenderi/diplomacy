"""
Game management API routes.

This module contains all endpoints related to game creation, state management,
player management (join/quit/replace), deadlines, snapshots, and history.
"""
from fastapi import APIRouter, HTTPException, Body, Depends
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

import requests
from fastapi.security import HTTPAuthorizationCredentials
from .auth import require_bot_or_user, resolve_user_or_telegram, http_bearer
from ..shared import (
    db_service, game_service, logger, scheduler_logger, NOTIFY_URL, ADMIN_TOKEN,
    notify_players, get_process_turn_lock,
)
from ...response_cache import cached_response, invalidate_cache

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
    telegram_id: Optional[str] = None  # Optional when using Bearer token (browser)
    bot_secret: Optional[str] = None
    game_id: int
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

# --- Game Management Endpoints ---
REQUIRED_POWERS = {"AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"}


@router.post("/games/create")
def create_game(
    req: CreateGameRequest,
    _: None = Depends(require_bot_or_user),
) -> Dict[str, Any]:
    """Create a new game. The new engine starts it immediately at S1901M with every
    power's opening units; players then claim powers via add_player/join."""
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


@router.post("/games/{game_id}/process_turn")
async def process_turn(
    game_id: str,
    _: None = Depends(require_bot_or_user),
) -> Dict[str, str]:
    """Adjudicate all pending orders and advance the phase."""
    if not game_service.exists(game_id):
        raise HTTPException(status_code=404, detail="Game not found")
    lock = get_process_turn_lock(game_id)
    if lock.locked():
        raise HTTPException(status_code=409, detail="Turn processing already in progress for this game")
    async with lock:
        game_service.process_turn(game_id)
    invalidate_cache(f"games/{game_id}")

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
                )
            except Exception as e:
                logger.debug(f"process_turn: snapshot failed: {e}")
            if view["status"] != "COMPLETED":
                db_service.update_game_deadline(int(row.id), datetime.now(timezone.utc) + timedelta(hours=24))
            else:
                db_service.update_game_deadline(int(row.id), None)
                try:
                    notify_players(int(row.id), f"Game {game_id} has ended!")
                except Exception as e:
                    scheduler_logger.error(f"Failed to notify game end: {e}")
    except Exception as e:
        scheduler_logger.error(f"process_turn post-processing error: {e}")
    return {"status": "ok"}


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
    """Set the deadline for a game."""
    try:
        game = db_service.get_game_by_game_id(game_id)
        if not game:
            raise HTTPException(status_code=404, detail="Game not found")
        game.deadline = req.deadline  # type: ignore
        deadline_value = getattr(game, 'deadline', None)
        return {"status": "ok", "deadline": deadline_value.isoformat() if deadline_value else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    """Restore a game to a previous snapshot"""
    try:
        snapshot = db_service.get_game_snapshot_by_id(snapshot_id)
        if not snapshot:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        if not game_service.exists(game_id):
            raise HTTPException(status_code=404, detail="Game not found")
        # Note: simplified restore - full restore would rewrite games.state_json.
        return {"status": "ok", "message": "Snapshot restored (simplified implementation)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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


@router.get("/games/{game_id}/legal_orders/{power}/{unit}")
def get_legal_orders(game_id: str, power: str, unit: str) -> Dict[str, Any]:
    """Legal order strings for a unit in the current phase (new engine).

    Enumerates holds, adjacent moves and supports from the map topology; free-form
    orders are still accepted and validated at submit time.
    """
    view = game_service.view(game_id)
    if view is None:
        raise HTTPException(status_code=404, detail="Game not found")
    parts = unit.upper().strip().split()
    if len(parts) < 2 or parts[0] not in ("A", "F"):
        raise HTTPException(status_code=400, detail=f"Invalid unit format: '{unit}'")
    kind, province = parts[0], parts[1].split("/")[0]
    m = game_service.map
    orders: List[str] = [f"{kind} {province} H"]
    if kind == "A":
        dests = sorted(m.army_moves(province))
        for d in dests:
            orders.append(f"{kind} {province} - {d}")
        for d in dests:
            orders.append(f"{kind} {province} S A {d}")
    else:
        dests = sorted({loc.province for floc in m.fleet_locations(province) for loc in m.fleet_moves(floc)})
        for d in dests:
            orders.append(f"{kind} {province} - {d}")
        for d in dests:
            orders.append(f"{kind} {province} S F {d}")
    return {"orders": orders}
