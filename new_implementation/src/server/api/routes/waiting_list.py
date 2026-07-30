"""Automatic game matching: the server-owned waiting list (G5).

This queue used to be ``telegram_bot/games.py``'s ``WAITING_LIST`` module global
-- an in-memory list with three defects:

1. **Dropped on every restart.** The bot is restarted on every deploy, so a
   partially filled queue vanished and the players in it waited forever for a
   game that would never be created.
2. **Its notification was a stub that only logged.** ``wait()`` passed a
   ``notify_callback`` whose whole body was
   ``logger.info(f"Would notify {telegram_id}: {message}")``, so when the 7th
   player joined, the six already queued got **nothing** -- only the 7th saw a
   reply, because that came from ``wait()``'s own ``reply_text``.
3. **Filling the queue was not atomic.** It created the game, joined seven
   players in a loop, and only then cleared the list. A failure inside the loop
   left an orphan game with a partial roster *and* an uncleared queue, so the
   next ``/wait`` tripped the threshold again and minted another orphan. It also
   took ``waiting_list[:required_size]`` but ``clear()``ed everything, silently
   dropping an 8th queued player.

The queue now lives in Postgres (``waiting_list`` table) and is owned here rather
than in the bot, which is meant to be a thin client over this API. Filling it
claims exactly ``WAITING_LIST_SIZE`` entries in one transaction *before* creating
anything, so a downstream failure re-queues precisely the players it took and can
never mint a second game from the same entries.
"""
import random
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import require_bot_or_user
from ..shared import NOTIFY_URL, db_service, game_service, logger, notify_players

router = APIRouter()

WAITING_LIST_SIZE = 7
POWERS = ["ENGLAND", "FRANCE", "GERMANY", "ITALY", "AUSTRIA", "RUSSIA", "TURKEY"]


class WaitingListRequest(BaseModel):
    """A player joining or leaving the queue.

    ``telegram_id`` is required: this endpoint exists for the Telegram bot, whose
    queue is keyed by Telegram identity, and a browser user has no place in a
    Telegram auto-match queue. Authentication is separate
    (``require_bot_or_user``) -- being authenticated does not let you queue
    somebody else, because the bot is trusted to pass the right id and is the
    only caller.
    """
    telegram_id: str
    full_name: Optional[str] = None


def _notify(telegram_id: str, message: str) -> None:
    """Best-effort DM through the bot's notification server.

    The same path ``api/shared.notify_players`` uses. Replaces G5's
    logging-only ``notify_callback``, which is why nobody in the queue was ever
    told their game had started.
    """
    try:
        telegram_id_int = int(telegram_id)
    except (TypeError, ValueError):
        logger.debug("Skipping waiting-list notification for non-numeric id %r", telegram_id)
        return
    try:
        requests.post(
            NOTIFY_URL,
            json={"telegram_id": telegram_id_int, "message": message},
            timeout=2,
        )
    except Exception as e:
        logger.warning(f"Failed to notify waiting-list player {telegram_id}: {e}")


def try_fill_waiting_list() -> Optional[Dict[str, Any]]:
    """Create a game if the queue is full. Returns ``None`` if it isn't.

    Ordering matters and is the whole point:

    1. **Claim** exactly ``WAITING_LIST_SIZE`` entries, removing them from the
       queue in one transaction. After this, no concurrent caller can build a
       second game from the same players.
    2. **Resolve every claimed player to a real user** *before* creating
       anything. An unlinked ``telegram_id`` is the one realistic failure, and
       this is what makes "create the game only once all seven joins are known to
       be possible" true rather than aspirational -- joins cannot be validated
       any earlier, since joining needs a game to exist.
    3. Create the game, then assign powers.

    Any failure re-queues the claimed entries (at the front -- they were nearly
    in a game and should not go to the back of the line for a server-side fault)
    and returns ``None``.
    """
    if db_service.count_waiting_list() < WAITING_LIST_SIZE:
        return None

    claimed = db_service.claim_waiting_list_entries(WAITING_LIST_SIZE)
    if not claimed:
        # Another worker won the race and took these entries.
        return None

    try:
        users = []
        for telegram_id, full_name in claimed:
            user = db_service.get_user_by_telegram_id(telegram_id)
            if user is None:
                raise ValueError(
                    f"telegram_id {telegram_id} is queued but has no registered user"
                )
            users.append((telegram_id, full_name, int(user.id)))

        shuffled = list(users)
        random.shuffle(shuffled)
        assignments: List[Tuple[str, Optional[str], int, str]] = [
            (telegram_id, full_name, user_id, power)
            for (telegram_id, full_name, user_id), power in zip(shuffled, POWERS)
        ]

        game_id = game_service.create_game(map_name="standard")
        row = db_service.get_game_by_game_id(str(game_id))
        if row is None:
            raise RuntimeError(f"game {game_id} was created but cannot be read back")

        for _telegram_id, _full_name, user_id, power in assignments:
            db_service.create_player(int(row.id), power, user_id=user_id)
    except Exception as e:
        db_service.requeue_waiting_list_entries(claimed)
        logger.error(
            "Failed to create a game from the waiting list; re-queued %d players: %s",
            len(claimed), e,
        )
        return None

    # Committed. Everything below is best-effort: a Telegram outage must not
    # undo a game that exists.
    for telegram_id, _full_name, _user_id, power in assignments:
        _notify(
            telegram_id,
            f"🎮 Game {game_id} created! You've been assigned {power}.\n\n"
            f"Use /games to see your game, /selectunit to order.",
        )
    try:
        notify_players(int(row.id), f"Game {game_id} is now full. Good luck to all players.")
    except Exception as e:
        logger.warning(f"Failed to post game-full notification for {game_id}: {e}")

    logger.info(
        "Created game %s from the waiting list with %d players", game_id, len(assignments)
    )
    return {
        "game_id": game_id,
        "assignments": {power: telegram_id for telegram_id, _f, _u, power in assignments},
    }


@router.post("/waiting_list/join")
def join_waiting_list(
    req: WaitingListRequest,
    _: None = Depends(require_bot_or_user),
) -> Dict[str, Any]:
    """Queue a player, creating a game immediately if that fills the queue.

    Idempotent: a repeated call reports ``already_queued`` rather than taking a
    second slot (``waiting_list.telegram_id`` is UNIQUE).
    """
    user = db_service.get_user_by_telegram_id(req.telegram_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="No registered user for this telegram_id -- register before joining the waiting list",
        )

    added = db_service.add_to_waiting_list(req.telegram_id, req.full_name)
    created = try_fill_waiting_list()

    return {
        "status": "queued" if added else "already_queued",
        "size": db_service.count_waiting_list(),
        "required": WAITING_LIST_SIZE,
        "game_created": created is not None,
        "game_id": created["game_id"] if created else None,
        "assignments": created["assignments"] if created else None,
    }


@router.post("/waiting_list/leave")
def leave_waiting_list(
    req: WaitingListRequest,
    _: None = Depends(require_bot_or_user),
) -> Dict[str, Any]:
    """Remove a player from the queue."""
    removed = db_service.remove_from_waiting_list(req.telegram_id)
    return {
        "status": "removed" if removed else "not_queued",
        "size": db_service.count_waiting_list(),
        "required": WAITING_LIST_SIZE,
    }


@router.get("/waiting_list")
def waiting_list_status() -> Dict[str, Any]:
    """How full the queue is. Read-only, no auth (same as other status reads).

    Deliberately returns counts, not the queued players' Telegram ids -- who is
    waiting for a game is not public information, and no client needs it.
    """
    size = db_service.count_waiting_list()
    return {
        "size": size,
        "required": WAITING_LIST_SIZE,
        "slots_remaining": max(0, WAITING_LIST_SIZE - size),
    }
