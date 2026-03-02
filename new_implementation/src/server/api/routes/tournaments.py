"""
Tournament management API routes.

Endpoints for creating and managing tournaments, linking games, and viewing brackets.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..shared import db_service, logger

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


# --- Request models ---
class CreateTournamentRequest(BaseModel):
    name: str
    bracket_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class AddGameToTournamentRequest(BaseModel):
    game_id: str
    round_number: int = 1
    bracket_position: Optional[str] = None


class AddPlayerToTournamentRequest(BaseModel):
    user_id: int
    seed: Optional[int] = None


class UpdateTournamentStatusRequest(BaseModel):
    status: str  # pending, active, completed, cancelled


@router.post("")
def create_tournament(req: CreateTournamentRequest) -> Dict[str, Any]:
    """Create a new tournament."""
    try:
        result = db_service.create_tournament(
            name=req.name,
            bracket_type=req.bracket_type,
            start_date=req.start_date,
            end_date=req.end_date,
        )
        return {"status": "ok", "tournament": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error creating tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_tournaments(status: Optional[str] = None) -> Dict[str, Any]:
    """List tournaments, optionally filtered by status."""
    try:
        tournaments = db_service.list_tournaments(status=status)
        return {"status": "ok", "tournaments": tournaments, "count": len(tournaments)}
    except Exception as e:
        logger.exception(f"Error listing tournaments: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tournament_id}")
def get_tournament(tournament_id: int) -> Dict[str, Any]:
    """Get tournament details by id."""
    try:
        tour = db_service.get_tournament(tournament_id)
        if not tour:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
        return {"status": "ok", "tournament": tour}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting tournament {tournament_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tournament_id}/bracket")
def get_tournament_bracket(tournament_id: int) -> Dict[str, Any]:
    """Get bracket view: tournament info, games by round, and players."""
    try:
        bracket = db_service.get_tournament_bracket(tournament_id)
        if "error" in bracket:
            raise HTTPException(status_code=404, detail=bracket["error"])
        return {"status": "ok", **bracket}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting bracket for tournament {tournament_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tournament_id}/games")
def add_game_to_tournament(tournament_id: int, req: AddGameToTournamentRequest) -> Dict[str, Any]:
    """Add a game to a tournament."""
    try:
        db_service.add_game_to_tournament(
            tournament_id=tournament_id,
            game_id=req.game_id,
            round_number=req.round_number,
            bracket_position=req.bracket_position,
        )
        return {
            "status": "ok",
            "message": f"Game {req.game_id} added to tournament {tournament_id}",
            "tournament_id": tournament_id,
            "game_id": req.game_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error adding game to tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tournament_id}/games")
def get_tournament_games(tournament_id: int) -> Dict[str, Any]:
    """List games in a tournament."""
    try:
        tour = db_service.get_tournament(tournament_id)
        if not tour:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
        games = db_service.get_tournament_games(tournament_id)
        return {"status": "ok", "tournament_id": tournament_id, "games": games}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error listing tournament games: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tournament_id}/players")
def add_player_to_tournament(tournament_id: int, req: AddPlayerToTournamentRequest) -> Dict[str, Any]:
    """Add a player to a tournament."""
    try:
        db_service.add_player_to_tournament(
            tournament_id=tournament_id,
            user_id=req.user_id,
            seed=req.seed,
        )
        return {
            "status": "ok",
            "message": f"Player {req.user_id} added to tournament {tournament_id}",
            "tournament_id": tournament_id,
            "user_id": req.user_id,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Error adding player to tournament: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tournament_id}/players")
def get_tournament_players(tournament_id: int) -> Dict[str, Any]:
    """List players in a tournament."""
    try:
        tour = db_service.get_tournament(tournament_id)
        if not tour:
            raise HTTPException(status_code=404, detail=f"Tournament {tournament_id} not found")
        players = db_service.get_tournament_players(tournament_id)
        return {"status": "ok", "tournament_id": tournament_id, "players": players}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error listing tournament players: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{tournament_id}/status")
def update_tournament_status(tournament_id: int, req: UpdateTournamentStatusRequest) -> Dict[str, Any]:
    """Update tournament status (pending, active, completed, cancelled)."""
    try:
        db_service.update_tournament_status(tournament_id, req.status)
        return {
            "status": "ok",
            "message": f"Tournament {tournament_id} status updated to {req.status}",
            "tournament_id": tournament_id,
            "new_status": req.status,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error updating tournament status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
