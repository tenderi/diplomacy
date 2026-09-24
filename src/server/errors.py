"""
Error handling utilities for the Diplomacy server.
"""
from enum import Enum
from typing import Dict, Any, Optional


class ErrorCode(Enum):
    """Standard error codes for server responses."""
    UNKNOWN_COMMAND = "UNKNOWN_COMMAND"
    MISSING_ARGUMENTS = "MISSING_ARGUMENTS"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    GAME_NOT_FOUND = "GAME_NOT_FOUND"
    POWER_NOT_FOUND = "POWER_NOT_FOUND"
    POWER_ALREADY_EXISTS = "POWER_ALREADY_EXISTS"
    INVALID_ORDER = "INVALID_ORDER"
    GAME_OVER = "GAME_OVER"
    FILE_ERROR = "FILE_ERROR"
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

    @staticmethod
    def game_not_found(game_id: str, command: str) -> Dict[str, Any]:
        """Error for non-existent game."""
        return ServerError.create_error_response(
            ErrorCode.GAME_NOT_FOUND,
            f"Game {game_id} not found for {command}",
            {"game_id": game_id, "command": command}
        )

    @staticmethod
    def power_not_found(power_name: str, game_id: str) -> Dict[str, Any]:
        """Error for non-existent power."""
        return ServerError.create_error_response(
            ErrorCode.POWER_NOT_FOUND,
            f"Power {power_name} not found in game {game_id}",
            {"power_name": power_name, "game_id": game_id}
        )

    @staticmethod
    def power_already_exists(power_name: str, game_id: str) -> Dict[str, Any]:
        """Error for duplicate power."""
        return ServerError.create_error_response(
            ErrorCode.POWER_ALREADY_EXISTS,
            f"Power {power_name} already exists in game {game_id}",
            {"power_name": power_name, "game_id": game_id}
        )

    @staticmethod
    def file_error(operation: str, filename: str, error_details: str) -> Dict[str, Any]:
        """Error for file operations."""
        return ServerError.create_error_response(
            ErrorCode.FILE_ERROR,
            f"Failed to {operation} {filename}: {error_details}",
            {"operation": operation, "filename": filename, "details": error_details}
        )

    @staticmethod
    def internal_error(operation: str, error_details: str) -> Dict[str, Any]:
        """Error for internal server errors."""
        return ServerError.create_error_response(
            ErrorCode.INTERNAL_ERROR,
            f"Internal error during {operation}: {error_details}",
            {"operation": operation, "details": error_details}
        )


class ServerResponse:
    """Utility class for creating consistent success responses."""

    @staticmethod
    def success(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a standardized success response."""
        response = {"status": "ok"}
        if data:
            response.update(data)
        return response

    @staticmethod
    def success_with_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a success response with data."""
        return ServerResponse.success(data)
