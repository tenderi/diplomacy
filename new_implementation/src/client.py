"""
Minimal client interface for testing and interacting with the server (CLI or API).
"""
from typing import Any, Dict

class Client:
    def __init__(self, server: Any):
        self.server = server
        self.last_response = None

    def send_command(self, command: str) -> Dict:
        self.last_response = self.server.process_command(command)
        return self.last_response

    def get_update(self) -> Dict:
        return self.last_response or {}
