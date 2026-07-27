"""Text-command server surface (CLI + DAIDE), backed by the new engine.

``Server.process_command`` is a thin adapter over ``GameService`` (game state /
adjudication) and ``DatabaseService`` (player assignments). It exists for the DAIDE
protocol and a handful of tests; the HTTP API talks to ``GameService`` directly.

The legacy in-memory ``self.games`` map is gone — game state lives in the database
(``games.state_json``) and is loaded per request. ``self.games`` remains as an empty
dict only so any not-yet-migrated caller does not ``AttributeError`` mid-cutover.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from .errors import ErrorCode, ServerError


class Server:
    def __init__(self) -> None:
        self.games: Dict[str, Any] = {}  # vestigial; game state lives in the DB
        self.next_game_id: int = 1
        self.logger = logging.getLogger("diplomacy.server")
        log_level = os.environ.get("DIPLOMACY_LOG_LEVEL", "INFO").upper()
        log_file = os.environ.get("DIPLOMACY_LOG_FILE")
        handler = logging.StreamHandler() if not log_file else logging.FileHandler(log_file)
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')
        handler.setFormatter(formatter)
        if not self.logger.hasHandlers():
            self.logger.addHandler(handler)
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))

    # -- service accessors (lazy to avoid an import cycle with shared) -----

    @property
    def _svc(self):
        from .api.shared import game_service
        return game_service

    @property
    def _db(self):
        from .api.shared import db_service
        return db_service

    def start(self) -> None:  # pragma: no cover - interactive CLI
        print("Diplomacy Server CLI. Type commands or 'QUIT' to exit.")
        while True:
            try:
                command = input('> ').strip()
                if command.upper() in ("QUIT", "EXIT"):
                    print("Shutting down server.")
                    break
                print(self.process_command(command))
            except (EOFError, KeyboardInterrupt):
                break

    def shutdown(self) -> None:
        self.logger.info("Diplomacy server shutting down.")

    def process_command(self, command: str) -> Dict[str, Any]:
        """Process a text command against the new engine."""
        tokens = command.strip().split()
        if not tokens:
            return ServerError.create_error_response(
                ErrorCode.MISSING_ARGUMENTS, "Empty command", {"command": command}
            )
        cmd = tokens[0].upper()
        try:
            if cmd in ("NEW_GAME", "CREATE_GAME"):
                map_name = tokens[1] if len(tokens) > 1 else "standard"
                game_id = str(self.next_game_id)
                self.next_game_id += 1
                self._svc.create_game(game_id, map_name=map_name)
                return {"status": "ok", "game_id": game_id, "map_name": map_name}

            if cmd == "ADD_PLAYER":
                if len(tokens) < 3:
                    return ServerError.missing_arguments(
                        "ADD_PLAYER", "ADD_PLAYER <game_id> <power_name>"
                    )
                game_id, power_name = tokens[1], tokens[2].upper()
                row = self._db.get_game_by_game_id(game_id)
                if row is None:
                    return ServerError.create_error_response(
                        ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id}
                    )
                self._db.create_player(int(row.id), power_name)
                return {"status": "ok"}

            if cmd == "SET_ORDERS":
                if len(tokens) < 4:
                    return ServerError.missing_arguments(
                        "SET_ORDERS", "SET_ORDERS <game_id> <power_name> <order_str>"
                    )
                game_id, power_name = tokens[1], tokens[2].upper()
                order_str = " ".join(tokens[3:])
                if not self._svc.exists(game_id):
                    return ServerError.create_error_response(
                        ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id}
                    )
                # One order per SET_ORDERS call, appended to the power's pending set.
                existing = self._svc.view(game_id)["orders"].get(power_name, [])
                self._svc.submit_orders(game_id, power_name, existing + [order_str])
                return {"status": "ok"}

            if cmd == "PROCESS_TURN":
                if len(tokens) < 2:
                    return ServerError.missing_arguments("PROCESS_TURN", "PROCESS_TURN <game_id>")
                game_id = tokens[1]
                if not self._svc.exists(game_id):
                    return ServerError.create_error_response(
                        ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id}
                    )
                self._svc.process_turn(game_id)
                return {"status": "ok"}

            if cmd in ("GET_GAME_STATE",):
                if len(tokens) < 2:
                    return ServerError.missing_arguments("GET_GAME_STATE", "GET_GAME_STATE <game_id>")
                game_id = tokens[1]
                view = self._svc.view(game_id)
                if view is None:
                    return ServerError.create_error_response(
                        ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id}
                    )
                return {"status": "ok", "state": view}

            return ServerError.unknown_command(cmd)
        except Exception as e:
            self.logger.exception(f"Exception while processing command '{command}': {e}")
            return ServerError.create_error_response(
                ErrorCode.INTERNAL_ERROR, f"Exception: {e}", {"command": command}
            )

    def get_game_state(self, game_id: str) -> Any:
        view = self._svc.view(str(game_id))
        if view is None:
            return ServerError.create_error_response(
                ErrorCode.GAME_NOT_FOUND, f"Game {game_id} not found", {"game_id": game_id}
            )
        return view
