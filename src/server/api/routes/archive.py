"""Saved-game export and import.

The old implementation could write a whole game to a JSON file
(``utils/export.py``'s ``to_saved_game_format``) and load it back -- that is how
its own regression fixtures were made and how the web UI's "Load a game from
disk" worked. The port dropped it: before this module a game could not leave the
database at all (Track W, from the pre-deletion audit of ``old_implementation/``).

**The export is the archival format**: everything needed to reconstruct a
finished game for analysis, a backup, or a replay fixture -- the final board, the
per-turn snapshots, and both halves of each turn (the orders given and what they
did, via ``resolution_history``). ``format`` is versioned so a later reader can
tell what it is holding.

**Both routes are admin-only**, and that is a deliberate privacy call rather than
laziness: a full export contains every private message in the game, so handing it
to a player would leak the diplomacy of the other six. A player-facing export
would have to filter ``messages`` the way ``GET /games/{id}/messages`` does; it
does not exist because nobody has asked for one.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .admin import require_admin
from ..shared import db_service, game_service, logger

router = APIRouter()

EXPORT_FORMAT = "diplomacy.game.v1"


class ImportGameRequest(BaseModel):
    """A document produced by ``GET /games/{id}/export``.

    Only ``state`` is strictly required -- everything else is restored when
    present, so a hand-written document with just a board is a valid way to set
    up a position (the old server's ``CreateGame(state=...)``).
    """
    format: Optional[str] = None
    game: Optional[Dict[str, Any]] = None
    state: Dict[str, Any]
    players: Optional[List[Dict[str, Any]]] = None
    order_history: Optional[Dict[str, Any]] = None
    resolution_history: Optional[Dict[str, Any]] = None
    last_resolution: Optional[Dict[str, Any]] = None
    snapshots: Optional[List[Dict[str, Any]]] = None
    messages: Optional[List[Dict[str, Any]]] = None


@router.get("/games/{game_id}/export", dependencies=[Depends(require_admin)])
def export_game(game_id: str) -> Dict[str, Any]:
    """The whole game as one JSON document. Admin only (contains private messages)."""
    row = db_service.get_game_by_game_id(str(game_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Game not found")
    state = game_service.state_json(str(game_id))
    if state is None:
        raise HTTPException(status_code=404, detail="Game has no state")
    meta = game_service.meta(str(game_id)) or {}
    creator_id = meta.get("created_by_user_id")
    creator = db_service.get_user_by_id(int(creator_id)) if creator_id is not None else None

    players = db_service.get_players_by_game_id(int(row.id))
    power_by_user: Dict[Any, str] = {}
    player_rows: List[Dict[str, Any]] = []
    for p in players:
        user = db_service.get_user_by_id(int(p.user_id)) if p.user_id is not None else None
        if p.user_id is not None:
            power_by_user[int(p.user_id)] = str(p.power_name)
        player_rows.append(
            {
                "power": p.power_name,
                # Identity is carried as the Telegram id, not the local numeric
                # user id: importing into another database has to re-link people,
                # and the numeric id means nothing there.
                "telegram_id": getattr(user, "telegram_id", None) if user is not None else None,
                "full_name": getattr(user, "full_name", None) if user is not None else None,
                "is_active": getattr(p, "is_active", None),
            }
        )

    messages = [
        {
            "sender_power": power_by_user.get(int(m.sender_user_id)),
            "recipient_power": m.recipient_power,
            "text": m.text,
            "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            "phase_code": m.phase_code,
        }
        for m in db_service.get_messages_by_game_id(int(row.id)).all()
    ]

    snapshots = [
        {
            "turn": s.turn_number,
            "phase_code": s.phase_code,
            "units": s.units,
            "supply_centers": s.supply_centers,
            "state": s.state_json,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in db_service.get_game_snapshots_by_game_id(int(row.id))
    ]

    return {
        "format": EXPORT_FORMAT,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "game": {
            "game_id": str(row.game_id),
            "map_name": meta.get("map_name", "standard"),
            "phase_code": meta.get("phase_code"),
            "status": meta.get("status"),
            "current_turn": meta.get("current_turn", 0),
            "phase_length_seconds": meta.get("phase_length_seconds"),
            # Settings carried so the imported game plays the same: who may
            # process early and change dummies, which powers are dummies (they
            # have no vote and nobody submits for them), and whether it runs
            # itself. The join password is not carried (data_spec: the hash is
            # never serialized), so an imported game comes back open.
            "created_by_telegram_id": getattr(creator, "telegram_id", None),
            "dummy_powers": meta.get("dummy_powers") or [],
            "auto_process": bool(meta.get("auto_process")),
        },
        "state": state,
        "players": player_rows,
        "order_history": game_service.order_history(str(game_id)),
        "resolution_history": game_service.resolution_history(str(game_id)),
        "last_resolution": game_service.last_resolution(str(game_id)),
        "snapshots": snapshots,
        "messages": messages,
    }


@router.post("/games/import", dependencies=[Depends(require_admin)])
def import_game(req: ImportGameRequest) -> Dict[str, Any]:
    """Recreate a game from an export document, under a **new** game id.

    Never overwrites an existing game: an import is a restore-alongside, so a
    botched one costs nothing. What can be restored depends on the target
    database -- people are re-linked by ``telegram_id``, so a power whose player
    has no account here is left unassigned, and a message whose sender cannot be
    resolved is skipped rather than being attributed to the wrong person. The
    response reports exactly what was and was not restored; check it rather than
    assuming a 200 means a complete restore.
    """
    if req.format is not None and req.format != EXPORT_FORMAT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export format {req.format!r}; expected {EXPORT_FORMAT!r}",
        )
    try:
        game_service.check_state_json(req.state)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Malformed state in the export: {e}") from e
    source = req.game or {}
    creator_telegram_id = source.get("created_by_telegram_id")
    creator = db_service.get_user_by_telegram_id(str(creator_telegram_id)) if creator_telegram_id else None
    try:
        game_id = game_service.create_game(
            map_name=str(source.get("map_name", "standard")),
            phase_length_seconds=source.get("phase_length_seconds"),
            created_by_user_id=int(creator.id) if creator is not None else None,
            dummy_powers=list(source.get("dummy_powers") or []),
            auto_process=bool(source.get("auto_process")),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Malformed game settings in the export: {e}") from e
    row = db_service.get_game_by_game_id(str(game_id))
    if row is None:  # pragma: no cover - create_game just wrote it
        raise HTTPException(status_code=500, detail="Imported game could not be read back")

    game_service.restore_snapshot(str(game_id), req.state, str(source.get("phase_code") or "S1901M"))

    game_service.import_histories(
        str(game_id),
        order_history=req.order_history,
        resolution_history=req.resolution_history,
        current_turn=source.get("current_turn"),
        last_resolution=req.last_resolution,
    )

    power_by_telegram: Dict[str, str] = {}
    players_linked, players_unlinked = 0, 0
    for entry in req.players or []:
        power = str(entry.get("power", "")).upper()
        telegram_id = entry.get("telegram_id")
        if not power:
            continue
        user = db_service.get_user_by_telegram_id(str(telegram_id)) if telegram_id else None
        if user is None:
            players_unlinked += 1
            continue
        db_service.create_player(int(row.id), power, user_id=int(user.id))
        power_by_telegram[power] = str(telegram_id)
        players_linked += 1

    user_id_by_power = {
        str(p.power_name): int(p.user_id)
        for p in db_service.get_players_by_game_id(int(row.id))
        if p.user_id is not None
    }
    messages_restored, messages_skipped = 0, 0
    for m in req.messages or []:
        sender_user_id = user_id_by_power.get(str(m.get("sender_power") or "").upper())
        if sender_user_id is None:
            messages_skipped += 1
            continue
        timestamp = m.get("timestamp")
        db_service.create_message(
            game_id=int(row.id),
            sender_user_id=sender_user_id,
            recipient_power=m.get("recipient_power"),
            text=str(m.get("text", "")),
            timestamp=datetime.fromisoformat(timestamp) if timestamp else None,
            phase_code=m.get("phase_code"),
        )
        messages_restored += 1

    snapshots_restored = 0
    for s in req.snapshots or []:
        try:
            db_service.create_game_snapshot(
                game_id=int(row.id),
                turn=int(s.get("turn", 0)),
                year=0,
                season="",
                phase="",
                phase_code=str(s.get("phase_code") or ""),
                game_state={
                    "units": s.get("units") or {},
                    "supply_centers": s.get("supply_centers") or {},
                },
                state_json=s.get("state"),
            )
            snapshots_restored += 1
        except Exception as e:
            logger.warning(f"Skipped a snapshot while importing game {game_id}: {e}")

    return {
        "status": "ok",
        "game_id": str(game_id),
        "creator_linked": creator is not None,
        "players_linked": players_linked,
        "players_unlinked": players_unlinked,
        "messages_restored": messages_restored,
        "messages_skipped": messages_skipped,
        "snapshots_restored": snapshots_restored,
    }
