# Diplomacy Server module

class Server:
    """Main class for accepting and processing game commands."""
    def __init__(self):
        self.games = []

    def process_command(self, command: str):
        """Accept and process a command. Returns a result or raises on error."""
        if command == "NEW_GAME":
            game_id = len(self.games) + 1
            self.games.append({"id": game_id, "status": "initialized"})
            return {"status": "ok", "game_id": game_id}
        else:
            return {"status": "error", "message": f"Unknown command: {command}"}
