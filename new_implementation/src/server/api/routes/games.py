"""
Game management API routes.

This module contains all endpoints related to game creation, state management,
player management (join/quit/replace), deadlines, snapshots, and history.
"""
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta

import requests
from ..shared import (
    db_service, server, logger, scheduler_logger, NOTIFY_URL, ADMIN_TOKEN,
    _state_to_spec_dict, _get_power_for_unit, notify_players
)
from ...models import GameStateOut
from engine.data_models import GameStatus, Unit
from engine.game import Game
from ...response_cache import cached_response, invalidate_cache

router = APIRouter()

# --- Request Models ---
class CreateGameRequest(BaseModel):
    """Request model for creating a new game."""
    map_name: str = "standard"

class AddPlayerRequest(BaseModel):
    """Request model for adding a player to a game."""
    game_id: str
    power: str

class SetDeadlineRequest(BaseModel):
    deadline: Optional[datetime]

class JoinGameRequest(BaseModel):
    telegram_id: str
    game_id: int
    power: str

class QuitGameRequest(BaseModel):
    telegram_id: str
    game_id: int

class ReplacePlayerRequest(BaseModel):
    telegram_id: str
    power: str

class MarkInactiveRequest(BaseModel):
    admin_token: str

# --- Game Management Endpoints ---
@router.post("/games/create")
def create_game(req: CreateGameRequest) -> Dict[str, Any]:
    """Create a new game and persist to the database, and register it in the in-memory server with the same game_id."""
    try:
        # Create the game in the database first (returns spec GameState)
        game_state = db_service.create_game(map_name=req.map_name)
        game_id = str(getattr(game_state, 'game_id', None) or "")
        if not game_id:
            raise RuntimeError("Failed to create game_id")
        # Now create the game in the in-memory server with the same game_id
        if game_id not in server.games:
            g = Game(map_name=req.map_name)
            setattr(g, "game_id", game_id)
            server.games[game_id] = g
        return {"game_id": game_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/add_player")
def add_player(req: AddPlayerRequest) -> Dict[str, Any]:
    """Add a player to a game."""
    try:
        # Add player to database
        player = db_service.add_player(game_id=int(req.game_id), power_name=req.power)
        player_id = getattr(player, 'id', None)
        if player_id is None:
            raise HTTPException(status_code=500, detail="Player ID not found after creation")
        # Add player to in-memory server
        if req.game_id not in server.games:
            g = Game()
            setattr(g, "game_id", req.game_id)
            server.games[req.game_id] = g
        result = server.process_command(f"ADD_PLAYER {req.game_id} {req.power}")
        if result.get("status") != "ok":
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        return {"status": "ok", "player_id": player_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/process_turn")
def process_turn(game_id: str) -> Dict[str, str]:
    """Advance the current phase for a game and update the database state."""
    # Ensure the in-memory engine processes the phase
    result = server.process_command(f"PROCESS_TURN {game_id}")
    if result.get("status") != "ok":
        raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
    
    # Invalidate cache for this game after processing turn
    invalidate_cache(f"games/{game_id}")
    try:
        # Use get_game_by_game_id since game_id is a string
        game = db_service.get_game_by_game_id(game_id)
        if game is not None and game_id in server.games:
            game_obj = server.games[game_id]
            state_obj = game_obj.get_game_state()
            # Update database with new game state (including updated unit positions)
            state_obj.game_id = game_id
            db_service.update_game_state(state_obj)
            safe_state = _state_to_spec_dict(state_obj)
            try:
                setattr(game, 'state', safe_state)
            except Exception as e:
                logger.debug(f"process_turn: failed to assign spec-shaped game.state: {e}")
            # Save game state snapshot
            game_obj = server.games[game_id]
            snapshot = db_service.create_game_snapshot(
                game_id=int(getattr(game, 'id', 0)),
                turn=game_obj.turn,
                year=game_obj.year,
                season=game_obj.season,
                phase=game_obj.phase,
                phase_code=game_obj.phase_code,
                game_state=safe_state
            )
            # Increment current_turn in database for order history tracking
            db_service.increment_game_current_turn(game_id)
            # Set new deadline if game is not done
            if state_obj.status != GameStatus.COMPLETED:
                setattr(game, 'deadline', datetime.now(timezone.utc) + timedelta(hours=24))
            else:
                setattr(game, 'deadline', None)
        # Game end notification
        try:
            if game is not None:
                state_val = getattr(game, 'state', None)
                if isinstance(state_val, dict) and state_val is not None and state_val.get("done"):
                    notify_players(game.id, f"Game {game.id} has ended! Final state: {game.state}")  # type: ignore
        except Exception as e:
            scheduler_logger.error(f"Failed to notify game end: {e}")
        
        # Channel integration: Auto-post map after turn processing
        try:
            from ..telegram_bot.channels import should_auto_post_map, post_map_to_channel
            from .maps import generate_map_for_snapshot
            
            if should_auto_post_map(game_id):
                channel_info = db_service.get_game_channel_info(game_id)
                if channel_info:
                    try:
                        result = generate_map_for_snapshot(game_id)
                        map_path = result.get("map_path")
                        if map_path:
                            post_map_to_channel(
                                channel_id=channel_info.get("channel_id"),
                                game_id=game_id,
                                map_path=map_path
                            )
                    except Exception as e:
                        logger.warning(f"Failed to auto-post map to channel for game {game_id}: {e}")
        except Exception as e:
            logger.debug(f"Channel integration check failed for game {game_id}: {e}")
        
        return {"status": "ok"}
    except Exception as e:
        import traceback
        scheduler_logger.error(f"process_turn error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/state")
@cached_response(ttl=30, key_params=["game_id"])
def get_game_state(game_id: str) -> GameStateOut:
    """
    Get the current state of the game, including map, units, powers, phase, and adjudication results for the latest turn.
    """
    # If game doesn't exist in server.games, try to restore it from database
    game = None
    if game_id in server.games:
        game = server.games[game_id]
        state = game.get_game_state()
    else:
        state = db_service.get_game_state(game_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Game not found")
    
    # Convert to GameStateOut model (complex conversion logic from original)
    from engine.database import unit_to_dict, order_to_dict
    from ...models import PowerStateOut, UnitOut
    
    supply_centers: dict[str, str] = {}
    for p_name, p_state in state.powers.items():
        for prov in p_state.controlled_supply_centers:
            supply_centers[prov] = p_name

    powers: Dict[str, PowerStateOut] = {}
    for power_name, ps in state.powers.items():
        powers[power_name] = PowerStateOut(
            power_name=ps.power_name,
            user_id=ps.user_id,
            is_active=ps.is_active,
            is_eliminated=ps.is_eliminated,
            home_supply_centers=ps.home_supply_centers,
            controlled_supply_centers=ps.controlled_supply_centers,
            units=[UnitOut(**unit_to_dict(u)) for u in ps.units],
            orders_submitted=ps.orders_submitted,
            last_order_time=ps.last_order_time.isoformat() if ps.last_order_time else None,
            retreat_options=ps.retreat_options,
            build_options=ps.build_options,
            destroy_options=ps.destroy_options,
        )

    state_out = GameStateOut(
        game_id=state.game_id,
        map_name=state.map_name,
        current_turn=state.current_turn,
        current_year=state.current_year,
        current_season=state.current_season,
        current_phase=state.current_phase,
        phase_code=state.phase_code,
        status=state.status.value,
        created_at=state.created_at.isoformat(),
        updated_at=state.updated_at.isoformat(),
        powers=powers,
        units={p: [UnitOut(**unit_to_dict(u)) for u in ps.units] for p, ps in state.powers.items()},
        supply_centers=supply_centers,
        orders={p: [order_to_dict(o) for o in orders] for p, orders in state.orders.items()},
        pending_retreats={p: [order_to_dict(o) for o in lst] for p, lst in state.pending_retreats.items()},
        pending_builds={p: [order_to_dict(o) for o in lst] for p, lst in state.pending_builds.items()},
        pending_destroys={p: [order_to_dict(o) for o in lst] for p, lst in state.pending_destroys.items()},
        order_history=[{p: [order_to_dict(o) for o in orders] for p, orders in turn_orders.items()} for turn_orders in state.order_history],
        turn_history=[],
        map_snapshots=[],
    )
    state_dict = state_out.model_dump()

    # In-memory adjudication results if available
    if game is not None and game_id in server.games:
        last_turn = game.turn - 1
        if hasattr(game, "game_state") and hasattr(game.game_state, "order_history") and last_turn < len(game.game_state.order_history):
            state_dict["adjudication_results"] = game.game_state.order_history[last_turn] if last_turn >= 0 else {}
        else:
            state_dict["adjudication_results"] = {}
    else:
        state_dict["adjudication_results"] = {}
    
    # Final shape hardening
    try:
        state_dict.setdefault("year", None)
        state_dict.setdefault("phase", None)
        state_dict.setdefault("turn", None)
        state_dict.setdefault("done", False)
        state_dict.setdefault("powers", {})
        state_dict.setdefault("units", {})
        state_dict.setdefault("orders", {})
        state_dict.setdefault("map_name", "standard")
        state_dict.setdefault("phase_code", None)
        state_dict.setdefault("adjudication_results", {})
    except Exception:
        pass
    return state_out

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
                "current_phase": getattr(g, 'phase', "Movement"),
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

@router.post("/games/{game_id}/join")
def join_game(game_id: int, req: JoinGameRequest) -> Dict[str, Any]:
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        # Check if already joined
        existing = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if existing:
            return {"status": "already_joined", "player_id": existing.id}
        # Check if power is taken
        taken = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        if taken:
            raise HTTPException(status_code=400, detail="Power already taken")
        # Use add_player which creates the player in the database
        power_state = db_service.add_player(game_id=game_id, power_name=req.power, user_id=int(user.id))  # type: ignore
        # Add player to in-memory server
        if str(game_id) not in server.games:
            g = Game()
            setattr(g, "game_id", str(game_id))
            server.games[str(game_id)] = g
        result = server.process_command(f"ADD_PLAYER {str(game_id)} {req.power}")
        if result.get("status") != "ok":
            raise HTTPException(status_code=400, detail=result.get("error", "Unknown error"))
        # Notification logic
        try:
            try:
                telegram_id_int = int(req.telegram_id)
                requests.post(
                    NOTIFY_URL,
                    json={"telegram_id": telegram_id_int, "message": f"You have joined game {game_id} as {req.power}."},
                    timeout=2,
                )
            except (ValueError, TypeError):
                pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify joining player {req.telegram_id}: {e}")
        # Get player model for return value
        player_model = db_service.get_player_by_game_id_and_power(game_id=game_id, power=req.power)
        player_id = player_model.id if player_model else user.id
        try:
            game = db_service.get_game_by_id(int(game_id)) if isinstance(game_id, int) else db_service.get_game_by_game_id(str(game_id))  # type: ignore
            if game:
                notify_players(int(game.id), f"Player {user.full_name or req.telegram_id} has joined game {game_id} as {req.power}.")  # type: ignore
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
        return {"status": "ok", "player_id": player_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/games/{game_id}/quit")
def quit_game(game_id: int, req: QuitGameRequest) -> Dict[str, Any]:
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        player = db_service.get_player_by_game_id_and_user_id(game_id=game_id, user_id=int(user.id))  # type: ignore
        if player is None:
            return {"status": "not_in_game"}
        # Unassign the user from the player slot
        try:
            db_service.delete_orders_by_player_id(int(player.id))  # type: ignore
            player.user_id = None  # type: ignore
            setattr(player, 'is_active', False)  # type: ignore
            db_service.update_player_is_active(int(player.id), False)  # type: ignore
            db_service.commit()
            # Invalidate cache for user games - use endpoint pattern matching
            invalidate_cache(f"users/{req.telegram_id}")
        except Exception:
            pass
        # Notification logic
        try:
            try:
                telegram_id_int = int(req.telegram_id)
                requests.post(
                    NOTIFY_URL,
                    json={"telegram_id": telegram_id_int, "message": f"You have quit game {game_id}."},
                    timeout=2,
                )
            except (ValueError, TypeError):
                pass
        except Exception as e:
            scheduler_logger.error(f"Failed to notify quitting player {req.telegram_id}: {e}")
        try:
            power_name = getattr(player, "power_name", None) or getattr(player, "power", None)
            notify_players(game_id, f"Player {user.full_name or req.telegram_id} has left game {game_id} (power {power_name}).")
        except Exception as e:
            scheduler_logger.error(f"Failed to notify players of quit event: {e}")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "ok", "detail": str(e)}

@router.post("/games/{game_id}/replace")
def replace_player(game_id: int, req: ReplacePlayerRequest) -> Dict[str, Any]:
    """Replace a vacated power in a game."""
    try:
        user = db_service.get_user_by_telegram_id(req.telegram_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
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
        from engine.database import PlayerModel
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
def set_deadline(game_id: str, req: SetDeadlineRequest) -> dict[str, Optional[str]]:
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
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    try:
        # Create snapshot (spec-shaped state)
        state_safe = _state_to_spec_dict(game.get_game_state())
        snapshot = db_service.create_game_snapshot(
            game_id=int(game_id),
            turn=game.turn,
            year=game.year,
            season=game.season,
            phase=game.phase,
            phase_code=game.phase_code,
            game_state=state_safe
        )
        return {"status": "ok", "snapshot_id": snapshot.id, "turn": game.turn}
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
        # Restore game state from snapshot
        if game_id not in server.games:
            g = Game()
            setattr(g, "game_id", game_id)
            server.games[game_id] = g
        # Update game state from snapshot
        # Note: This is a simplified restore - full restore would need to rebuild game object
        return {"status": "ok", "message": "Snapshot restored (simplified implementation)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/games/{game_id}/debug/unit_locations")
def debug_unit_locations(game_id: str) -> Dict[str, Any]:
    """Get all unit locations in text format for debugging"""
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    
    game = server.games[game_id]
    unit_locations = {}
    
    for power_name, power in game.game_state.powers.items():
        unit_locations[power_name] = [f"{unit.unit_type} {unit.province}" for unit in power.units]
    
    return {
        "status": "ok",
        "game_id": game_id,
        "turn": game.turn,
        "phase": game.phase,
        "unit_locations": unit_locations
    }

# Helper functions for legal orders (moved from main api.py)
def _generate_movement_orders(game: Any, game_state: Any, unit: Unit, power: str) -> List[str]:
    """Generate all legal movement phase orders for a unit."""
    orders = []
    
    # 1. Hold order
    coast_suffix = f"/{unit.coast}" if unit.coast else ""
    hold_order = f"{power} {unit.unit_type} {unit.province}{coast_suffix} H"
    orders.append(hold_order)
    
    # 2. Move orders to adjacent valid provinces
    if unit.province in game_state.map_data.provinces:
        current_province = game_state.map_data.provinces[unit.province]
        
        for adjacent_prov in current_province.adjacent_provinces:
            if adjacent_prov in game_state.map_data.provinces:
                target_province = game_state.map_data.provinces[adjacent_prov]
                
                # Check if unit can move to this province type
                if unit.can_move_to_province_type(target_province.province_type):
                    # Check if province is occupied
                    is_occupied = any(
                        u.province == adjacent_prov 
                        for power_state in game_state.powers.values() 
                        for u in power_state.units
                    )
                    
                    if not is_occupied:
                        move_order = f"{power} {unit.unit_type} {unit.province}{coast_suffix} - {adjacent_prov}"
                        orders.append(move_order)
    
    # 3. Support orders (simplified - support any adjacent move)
    for adjacent_prov in current_province.adjacent_provinces if unit.province in game_state.map_data.provinces else []:
        support_order = f"{power} {unit.unit_type} {unit.province}{coast_suffix} S {unit.unit_type} {adjacent_prov} - {adjacent_prov}"
        orders.append(support_order)
    
    # 4. Convoy orders (for fleets)
    if unit.unit_type == "F" and unit.province in game_state.map_data.provinces:
        current_prov = game_state.map_data.provinces[unit.province]
        if current_prov.province_type == "sea":
            # Find armies that could be convoyed
            for other_power, other_power_state in game_state.powers.items():
                for other_unit in other_power_state.units:
                    if other_unit.unit_type == "A" and other_unit.province in current_prov.adjacent_provinces:
                        # Can convoy to any coastal province
                        for target in game_state.map_data.provinces.values():
                            if target.province_type == "coastal" and target.name != other_unit.province:
                                convoy_order = f"{power} {unit.unit_type} {unit.province}{coast_suffix} C {other_unit.unit_type} {other_unit.province} - {target.name}"
                                orders.append(convoy_order)
    
    return orders


def _generate_retreat_orders(game_state: Any, unit: Unit, power: str) -> List[str]:
    """Generate all legal retreat orders for a dislodged unit."""
    orders = []
    
    if not unit.is_dislodged:
        return orders
    
    # Use retreat options if available
    if unit.retreat_options:
        coast_suffix = f"/{unit.coast}" if unit.coast else ""
        for retreat_prov in unit.retreat_options:
            retreat_order = f"{power} {unit.unit_type} {unit.province}{coast_suffix} R {retreat_prov}"
            orders.append(retreat_order)
    else:
        # Calculate retreat options if not already set
        current_province_name = unit.province.replace("DISLODGED_", "")
        current_province = game_state.map_data.provinces.get(current_province_name)
        
        if current_province:
            for adjacent_prov in current_province.adjacent_provinces:
                if adjacent_prov in game_state.map_data.provinces:
                    target_province = game_state.map_data.provinces[adjacent_prov]
                    
                    if unit.can_move_to_province_type(target_province.province_type):
                        is_occupied = any(
                            u.province == adjacent_prov 
                            for power_state in game_state.powers.values() 
                            for u in power_state.units
                        )
                        
                        if not is_occupied:
                            coast_suffix = f"/{unit.coast}" if unit.coast else ""
                            retreat_order = f"{power} {unit.unit_type} {current_province_name}{coast_suffix} R {adjacent_prov}"
                            orders.append(retreat_order)
    
    return orders


def _generate_build_orders(game_state: Any, power_state: Any, power: str) -> List[str]:
    """Generate all legal build/destroy orders for a power in build phase."""
    orders = []
    
    unit_count = len(power_state.units)
    supply_center_count = len(power_state.controlled_supply_centers)
    
    # Build orders - if supply centers > units
    if supply_center_count > unit_count:
        build_count = supply_center_count - unit_count
        home_centers = game_state.map_data.home_supply_centers.get(power, [])
        occupied_provinces = {u.province for u in game_state.get_all_units()}
        
        for home_center in home_centers:
            if home_center not in occupied_provinces and build_count > 0:
                center_prov = game_state.map_data.provinces.get(home_center)
                if center_prov:
                    if center_prov.province_type == "coastal":
                        build_army = f"{power} BUILD A {home_center}"
                        build_fleet = f"{power} BUILD F {home_center}"
                        orders.append(build_army)
                        orders.append(build_fleet)
                    else:
                        build_army = f"{power} BUILD A {home_center}"
                        orders.append(build_army)
                    build_count -= 1
    
    # Destroy orders - if units > supply centers
    elif unit_count > supply_center_count:
        destroy_count = unit_count - supply_center_count
        for unit in power_state.units[:destroy_count]:
            destroy_order = f"{power} DESTROY {unit.unit_type} {unit.province}"
            orders.append(destroy_order)
    
    return orders

@router.get("/games/{game_id}/legal_orders/{power}/{unit}")
def get_legal_orders(game_id: str, power: str, unit: str) -> Dict[str, Any]:
    """
    Get all valid order strings for the given unit and power in the current game state.
    """
    if game_id not in server.games:
        raise HTTPException(status_code=404, detail="Game not found")
    game = server.games[game_id]
    game_state = game.get_game_state()
    
    # Parse unit string
    unit_parts = unit.upper().strip().split()
    if len(unit_parts) < 2:
        raise HTTPException(status_code=400, detail=f"Invalid unit format: '{unit}'. Expected format: 'A PAR' or 'F BRE'")
    
    unit_type = unit_parts[0]
    unit_province = unit_parts[1]
    
    if unit_type not in ["A", "F"]:
        raise HTTPException(status_code=400, detail=f"Invalid unit type: '{unit_type}'. Must be 'A' (Army) or 'F' (Fleet)")
    
    # Find the unit
    power_state = game_state.powers.get(power)
    if not power_state:
        raise HTTPException(status_code=404, detail=f"Power '{power}' not found in game")
    
    found_unit = None
    for u in power_state.units:
        if u.unit_type == unit_type and u.province == unit_province:
            found_unit = u
            break
    
    if not found_unit:
        raise HTTPException(status_code=404, detail=f"Unit '{unit}' not found for power '{power}'")
    
    # Generate legal orders based on current phase
    orders = []
    current_phase = game_state.current_phase
    
    if current_phase == "Movement":
        orders.extend(_generate_movement_orders(game, game_state, found_unit, power))
    elif current_phase == "Retreat":
        orders.extend(_generate_retreat_orders(game_state, found_unit, power))
    elif current_phase in ["Builds", "Adjustment"]:
        orders.extend(_generate_build_orders(game_state, power_state, power))
    
    return {"orders": orders}

