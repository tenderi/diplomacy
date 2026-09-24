"""
Error handling utilities for the Diplomacy server.
"""
from enum import Enum
from typing import Dict, Any, Optional


class ErrorCode(Enum):
    """Standard error codes for server responses."""
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    MISSING_ARGUMENTS = "MISSING_ARGUMENTS"
    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    INVALID_ORDER = "INVALID_ORDER"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ServerError:
    """Utility class for creating consistent error responses."""

    @staticmethod
    def create_error_response(
        error_code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a standardized error response."""
        response = {
            "status": "error",
            "error_code": error_code.value,
            "message": message
        }

        if details:
            response.update(details)

        return response

    @staticmethod
    def unknown_command(command: str) -> Dict[str, Any]:
        """Error for unknown commands."""
        return ServerError.create_error_response(
            ErrorCode.UNKNOWN_COMMAND,
            f"Unknown command: {command}",
            {"command": command}
        )

    @staticmethod
    def missing_arguments(command: str, usage: str) -> Dict[str, Any]:
        """Error for missing command arguments."""
        return ServerError.create_error_response(
            ErrorCode.MISSING_ARGUMENTS,
            f"{command} missing arguments",
            {"command": command, "usage": usage}
        )
