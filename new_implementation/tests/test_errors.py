"""
Comprehensive tests for server error handling utilities.

Tests cover:
- ErrorCode enum
- ServerError utility methods
- ServerResponse utility methods
- Error response format consistency
"""
import pytest
from server.errors import ErrorCode, ServerError, ServerResponse


class TestErrorCode:
    """Test ErrorCode enum."""
    
    def test_error_code_values(self):
        """Test all error code enum values."""
        assert ErrorCode.UNKNOWN_COMMAND.value == "UNKNOWN_COMMAND"
        assert ErrorCode.MISSING_ARGUMENTS.value == "MISSING_ARGUMENTS"
        assert ErrorCode.INVALID_ARGUMENTS.value == "INVALID_ARGUMENTS"
        assert ErrorCode.GAME_NOT_FOUND.value == "GAME_NOT_FOUND"
        assert ErrorCode.POWER_NOT_FOUND.value == "POWER_NOT_FOUND"
        assert ErrorCode.POWER_ALREADY_EXISTS.value == "POWER_ALREADY_EXISTS"
        assert ErrorCode.INVALID_ORDER.value == "INVALID_ORDER"
        assert ErrorCode.GAME_OVER.value == "GAME_OVER"
        assert ErrorCode.FILE_ERROR.value == "FILE_ERROR"
        assert ErrorCode.INTERNAL_ERROR.value == "INTERNAL_ERROR"
    
    def test_error_code_enum_membership(self):
        """Test that error codes are proper enum members."""
        assert isinstance(ErrorCode.UNKNOWN_COMMAND, ErrorCode)
        assert isinstance(ErrorCode.MISSING_ARGUMENTS, ErrorCode)
        assert isinstance(ErrorCode.INTERNAL_ERROR, ErrorCode)


class TestServerError:
    """Test ServerError utility class."""
    
    def test_create_error_response_basic(self):
        """Test basic error response creation."""
        response = ServerError.create_error_response(
            ErrorCode.UNKNOWN_COMMAND,
            "Test error message"
        )
        
        assert response["status"] == "error"
        assert response["error_code"] == "UNKNOWN_COMMAND"
        assert response["message"] == "Test error message"
    
    def test_create_error_response_with_details(self):
        """Test error response with additional details."""
        details = {"command": "INVALID", "line": 42}
        response = ServerError.create_error_response(
            ErrorCode.INVALID_ARGUMENTS,
            "Invalid arguments provided",
            details=details
        )
        
        assert response["status"] == "error"
        assert response["error_code"] == "INVALID_ARGUMENTS"
        assert response["message"] == "Invalid arguments provided"
        assert response["command"] == "INVALID"
        assert response["line"] == 42
    
    def test_unknown_command(self):
        """Test unknown_command error helper."""
        response = ServerError.unknown_command("FAKE_COMMAND")
        
        assert response["status"] == "error"
        assert response["error_code"] == "UNKNOWN_COMMAND"
        assert "Unknown command: FAKE_COMMAND" in response["message"]
        assert response["command"] == "FAKE_COMMAND"
    
    def test_missing_arguments(self):
        """Test missing_arguments error helper."""
        response = ServerError.missing_arguments("CREATE_GAME", "CREATE_GAME <map_name>")
        
        assert response["status"] == "error"
        assert response["error_code"] == "MISSING_ARGUMENTS"
        assert "CREATE_GAME missing arguments" in response["message"]
        assert response["command"] == "CREATE_GAME"
        assert response["usage"] == "CREATE_GAME <map_name>"
    
    def test_game_not_found(self):
        """Test game_not_found error helper."""
        response = ServerError.game_not_found("game_123", "PROCESS_TURN")
        
        assert response["status"] == "error"
        assert response["error_code"] == "GAME_NOT_FOUND"
        assert "Game game_123 not found" in response["message"]
        assert response["game_id"] == "game_123"
        assert response["command"] == "PROCESS_TURN"
    
    def test_power_not_found(self):
        """Test power_not_found error helper."""
        response = ServerError.power_not_found("FRANCE", "game_123")
        
        assert response["status"] == "error"
        assert response["error_code"] == "POWER_NOT_FOUND"
        assert "Power FRANCE not found" in response["message"]
        assert response["power_name"] == "FRANCE"
        assert response["game_id"] == "game_123"
    
    def test_power_already_exists(self):
        """Test power_already_exists error helper."""
        response = ServerError.power_already_exists("FRANCE", "game_123")
        
        assert response["status"] == "error"
        assert response["error_code"] == "POWER_ALREADY_EXISTS"
        assert "Power FRANCE already exists" in response["message"]
        assert response["power_name"] == "FRANCE"
        assert response["game_id"] == "game_123"
    
    def test_file_error(self):
        """Test file_error error helper."""
        response = ServerError.file_error("read", "config.json", "Permission denied")
        
        assert response["status"] == "error"
        assert response["error_code"] == "FILE_ERROR"
        assert "Failed to read config.json" in response["message"]
        assert response["operation"] == "read"
        assert response["filename"] == "config.json"
        assert response["details"] == "Permission denied"
    
    def test_internal_error(self):
        """Test internal_error error helper."""
        response = ServerError.internal_error("process_turn", "Database connection failed")
        
        assert response["status"] == "error"
        assert response["error_code"] == "INTERNAL_ERROR"
        assert "Internal error during process_turn" in response["message"]
        assert response["operation"] == "process_turn"
        assert response["details"] == "Database connection failed"


class TestServerResponse:
    """Test ServerResponse utility class."""
    
    def test_success_basic(self):
        """Test basic success response."""
        response = ServerResponse.success()
        
        assert response["status"] == "ok"
        assert len(response) == 1  # Only status field
    
    def test_success_with_data(self):
        """Test success response with data."""
        data = {"game_id": "123", "turn": 1}
        response = ServerResponse.success(data)
        
        assert response["status"] == "ok"
        assert response["game_id"] == "123"
        assert response["turn"] == 1
    
    def test_success_with_data_method(self):
        """Test success_with_data helper method."""
        data = {"result": "success", "count": 42}
        response = ServerResponse.success_with_data(data)
        
        assert response["status"] == "ok"
        assert response["result"] == "success"
        assert response["count"] == 42
    
    def test_success_with_nested_data(self):
        """Test success response with nested data."""
        data = {
            "game": {
                "id": "123",
                "status": "active"
            },
            "players": ["FRANCE", "GERMANY"]
        }
        response = ServerResponse.success(data)
        
        assert response["status"] == "ok"
        assert response["game"]["id"] == "123"
        assert response["players"] == ["FRANCE", "GERMANY"]


class TestErrorResponseConsistency:
    """Test error response format consistency."""
    
    def test_all_error_methods_return_consistent_format(self):
        """Test that all error methods return consistent format."""
        error_methods = [
            lambda: ServerError.unknown_command("TEST"),
            lambda: ServerError.missing_arguments("TEST", "usage"),
            lambda: ServerError.game_not_found("123", "CMD"),
            lambda: ServerError.power_not_found("FRANCE", "123"),
            lambda: ServerError.power_already_exists("FRANCE", "123"),
            lambda: ServerError.file_error("op", "file", "error"),
            lambda: ServerError.internal_error("op", "error"),
        ]
        
        for error_method in error_methods:
            response = error_method()
            
            # All error responses should have these fields
            assert "status" in response
            assert response["status"] == "error"
            assert "error_code" in response
            assert "message" in response
            
            # Error code should be a string
            assert isinstance(response["error_code"], str)
            
            # Message should be a string
            assert isinstance(response["message"], str)
    
    def test_success_responses_consistent_format(self):
        """Test that success responses have consistent format."""
        responses = [
            ServerResponse.success(),
            ServerResponse.success({"data": "value"}),
            ServerResponse.success_with_data({"key": "value"}),
        ]
        
        for response in responses:
            assert "status" in response
            assert response["status"] == "ok"

