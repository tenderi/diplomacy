"""
Minimal client interface for testing and interacting with the server (CLI or API).
"""
from typing import Any, Dict

class Client:
    def __init__(self, server: Any) -> None:
        self.server: Any = server
        self.last_response: Any = None

    def send_command(self, command: str) -> Dict[str, Any]:
        self.last_response = self.server.process_command(command)
        return self.last_response

    def get_update(self) -> Dict[str, Any]:
        return self.last_response or {}
