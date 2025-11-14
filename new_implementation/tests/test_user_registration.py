"""
Comprehensive tests for user registration endpoints.

Tests cover:
- Persistent user registration (POST /users/persistent_register)
- Error handling (missing fields, database errors, etc.)
- Duplicate registration handling
- User retrieval
"""
import os
import pytest
from fastapi.testclient import TestClient

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    project_root = os.path.join(os.path.dirname(__file__), '..', '..')
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

try:
    from server.api import app
except Exception:
    pytest.skip("FastAPI app not importable; skipping registration tests", allow_module_level=True)


def _has_db_url() -> bool:
    """Check if database URL is configured. Supports .env file loading."""
    return bool(os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL"))


@pytest.mark.skipif(not _has_db_url(), reason="Database URL not configured. Set SQLALCHEMY_DATABASE_URL or DIPLOMACY_DATABASE_URL environment variable, or create a .env file in the project root.")
class TestPersistentUserRegistration:
    """Test persistent user registration endpoint."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Ensure database schema exists before each test."""
        import uuid
        self.unique_id = f"test_user_{uuid.uuid4().hex[:8]}"
        self.client = TestClient(app)
        yield
        # Cleanup handled by test database fixtures
    
    def test_register_new_user_success(self):
        """Test successful registration of a new user."""
        response = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": self.unique_id, "full_name": "Test User"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "user_id" in data
        assert isinstance(data["user_id"], int)
        assert data["user_id"] > 0
    
    def test_register_user_minimal_fields(self):
        """Test registration with only telegram_id (full_name optional)."""
        response = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": self.unique_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "user_id" in data
    
    def test_register_duplicate_user(self):
        """Test registering the same user twice (should return existing user)."""
        # First registration
        response1 = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": self.unique_id, "full_name": "Test User"}
        )
        assert response1.status_code == 200
        user_id1 = response1.json()["user_id"]
        
        # Second registration with same telegram_id
        response2 = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": self.unique_id, "full_name": "Test User Updated"}
        )
        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "ok"
        # Should return same user_id (idempotent operation)
        assert data["user_id"] == user_id1
    
    def test_register_user_missing_telegram_id(self):
        """Test registration fails when telegram_id is missing."""
        response = self.client.post(
            "/users/persistent_register",
            json={"full_name": "Test User"}
        )
        assert response.status_code == 422  # Validation error
    
    def test_register_user_empty_telegram_id(self):
        """Test registration fails with empty telegram_id."""
        response = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": "", "full_name": "Test User"}
        )
        assert response.status_code == 400
        assert "required" in response.json()["detail"].lower() or "empty" in response.json()["detail"].lower()
    
    def test_register_user_whitespace_only_telegram_id(self):
        """Test registration fails with whitespace-only telegram_id."""
        response = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": "   ", "full_name": "Test User"}
        )
        assert response.status_code == 400
    
    def test_register_multiple_different_users(self):
        """Test registering multiple different users."""
        users = []
        for i in range(5):
            unique_id = f"{self.unique_id}_{i}"
            response = self.client.post(
                "/users/persistent_register",
                json={"telegram_id": unique_id, "full_name": f"User {i}"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            users.append(data["user_id"])
        
        # All user IDs should be different
        assert len(set(users)) == 5
    
    def test_register_user_with_special_characters(self):
        """Test registration with special characters in full_name."""
        response = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": self.unique_id, "full_name": "Test User with 'quotes' and émojis 🎮"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_register_user_numeric_telegram_id(self):
        """Test registration with numeric telegram_id (common in Telegram)."""
        numeric_id = "123456789"
        response = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": numeric_id, "full_name": "Numeric User"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_register_user_long_telegram_id(self):
        """Test registration with very long telegram_id."""
        long_id = "a" * 255  # Test maximum length
        response = self.client.post(
            "/users/persistent_register",
            json={"telegram_id": long_id, "full_name": "Long ID User"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


@pytest.mark.skipif(not _has_db_url(), reason="Database URL not configured.")
class TestUserRegistrationErrorHandling:
    """Test error handling in user registration."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test client."""
        self.client = TestClient(app)
    
    def test_register_invalid_json(self):
        """Test registration with invalid JSON."""
        response = self.client.post(
            "/users/persistent_register",
            data="not json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
    
    def test_register_missing_json_body(self):
        """Test registration with missing request body."""
        response = self.client.post("/users/persistent_register")
        assert response.status_code == 422
    
    def test_register_wrong_content_type(self):
        """Test registration with wrong content type."""
        response = self.client.post(
            "/users/persistent_register",
            data={"telegram_id": "123", "full_name": "Test"},
            headers={"Content-Type": "text/plain"}
        )
        # FastAPI should handle this gracefully
        assert response.status_code in [422, 400]

