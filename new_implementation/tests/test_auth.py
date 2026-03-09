"""
Tests for auth routes: register, login, refresh, me, link_code, telegram/link.
Also tests game routes using Bearer token (join, set_orders).
"""
import os
import time
import pytest

try:
    from dotenv import load_dotenv
    _root = os.path.join(os.path.dirname(__file__), "..")
    _env = os.path.join(_root, ".env")
    if os.path.exists(_env):
        load_dotenv(_env)
except ImportError:
    pass


def _get_db_url():
    return os.environ.get("SQLALCHEMY_DATABASE_URL") or os.environ.get("DIPLOMACY_DATABASE_URL")


def _unique_email(prefix="auth"):
    """Return a unique email for tests to avoid duplicate-key conflicts."""
    return f"{prefix}_{int(time.time() * 1000)}@example.com"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from server.api import app
    return TestClient(app)


def _skip_if_no_db():
    if not _get_db_url():
        pytest.skip("Database URL not configured (SQLALCHEMY_DATABASE_URL)")




def test_register_and_login(client):
    """Register with email/password then login returns tokens and user."""
    _skip_if_no_db()
    email = _unique_email("register")
    password = "testpass123"

    reg = client.post("/auth/register", json={
        "email": email,
        "password": password,
        "full_name": "Auth Test User",
    })
    assert reg.status_code == 200
    data = reg.json()
    # Shape expected by browser frontend (AuthContext)
    assert "access_token" in data
    assert "refresh_token" in data
    assert "user" in data
    assert data["user"]["email"] == email
    assert "password" not in str(data)

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    login_data = login.json()
    assert "access_token" in login_data
    assert login_data["user"]["email"] == email


def test_register_duplicate_email(client):
    """Registering same email twice returns 400."""
    _skip_if_no_db()
    email = _unique_email("dup")
    client.post("/auth/register", json={"email": email, "password": "pass12345"})
    reg2 = client.post("/auth/register", json={"email": email, "password": "other12345"})
    assert reg2.status_code == 400


def test_register_invalid_email_format(client):
    """Register with invalid email returns 400."""
    _skip_if_no_db()
    resp = client.post("/auth/register", json={"email": "not-an-email", "password": "pass12345"})
    assert resp.status_code == 400
    assert "email" in (resp.json().get("detail") or "").lower()


def test_register_short_password(client):
    """Register with password < 8 chars returns 422 with a readable detail (for frontend)."""
    _skip_if_no_db()
    resp = client.post("/auth/register", json={"email": _unique_email("short"), "password": "short"})
    assert resp.status_code == 422
    data = resp.json()
    detail = data.get("detail")
    assert detail is not None
    if isinstance(detail, list):
        assert len(detail) >= 1
        msg = detail[0].get("msg", "")
        assert "8" in msg or "password" in msg.lower()
    else:
        assert "8" in str(detail) or "password" in str(detail).lower()


def test_login_nonexistent_email(client):
    """Login with unknown email returns 401."""
    _skip_if_no_db()
    resp = client.post("/auth/login", json={"email": "nobody@example.com", "password": "pass12345"})
    assert resp.status_code == 401


def test_login_wrong_password(client):
    """Login with wrong password returns 401."""
    _skip_if_no_db()
    email = _unique_email("wrongpw")
    client.post("/auth/register", json={"email": email, "password": "pass12345"})
    resp = client.post("/auth/login", json={"email": email, "password": "wrongpassword"})
    assert resp.status_code == 401


def test_token_oauth2_endpoint(client):
    """POST /auth/token (OAuth2 form) works with username=email and password."""
    _skip_if_no_db()
    email = _unique_email("token")
    password = "pass12345"
    client.post("/auth/register", json={"email": email, "password": password})
    resp = client.post(
        "/auth/token",
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()


def test_token_oauth2_invalid(client):
    """POST /auth/token with wrong password returns 401."""
    _skip_if_no_db()
    email = _unique_email("token_inv")
    client.post("/auth/register", json={"email": email, "password": "pass12345"})
    resp = client.post(
        "/auth/token",
        data={"username": email, "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 401


def test_refresh_invalid_token(client):
    """POST /auth/refresh with invalid token returns 401."""
    _skip_if_no_db()
    resp = client.post("/auth/refresh", json={"refresh_token": "invalid-token"})
    assert resp.status_code == 401


def test_unlink_when_not_linked(client):
    """POST /auth/me/unlink_telegram when no Telegram linked returns 200 with message."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={
        "email": _unique_email("unlink_none"),
        "password": "pass12345",
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    unlink = client.post("/auth/me/unlink_telegram", headers={"Authorization": f"Bearer {token}"})
    assert unlink.status_code == 200
    assert "no telegram" in unlink.json().get("message", "").lower() or "unlink" in unlink.json().get("message", "").lower()


def test_reset_password_invalid_token(client):
    """POST /auth/reset_password with invalid token returns 400."""
    _skip_if_no_db()
    resp = client.post("/auth/reset_password", json={"token": "invalid", "new_password": "newpass123"})
    assert resp.status_code == 400


def test_reset_password_short_password(client):
    """POST /auth/reset_password with short password returns 422."""
    _skip_if_no_db()
    resp = client.post("/auth/reset_password", json={"token": "sometoken", "new_password": "short"})
    assert resp.status_code == 422


def test_forgot_password_invalid_email_still_200(client):
    """POST /auth/forgot_password with invalid email still returns 200 (no enumeration)."""
    _skip_if_no_db()
    resp = client.post("/auth/forgot_password", json={"email": "not-an-email"})
    assert resp.status_code == 200
    assert "message" in resp.json()


def test_forgot_password_with_base_url_no_dev_link(client):
    """POST /auth/forgot_password with base_url set but no DEV_SHOW_RESET_LINK (covers _send else branch)."""
    _skip_if_no_db()
    email = _unique_email("forgot_no_dev")
    client.post("/auth/register", json={"email": email, "password": "pass12345"})
    saved = os.environ.pop("DIPLOMACY_DEV_SHOW_RESET_LINK", None)
    os.environ["DIPLOMACY_PASSWORD_RESET_BASE_URL"] = "http://test.example.com"
    try:
        resp = client.post("/auth/forgot_password", json={"email": email})
        assert resp.status_code == 200
        assert "message" in resp.json()
        assert "reset_link" not in resp.json()
    finally:
        if saved is not None:
            os.environ["DIPLOMACY_DEV_SHOW_RESET_LINK"] = saved
        os.environ.pop("DIPLOMACY_PASSWORD_RESET_BASE_URL", None)


def test_telegram_link_already_linked_to_other_account(client):
    """POST /auth/telegram/link when telegram_id already linked to another user returns 409."""
    _skip_if_no_db()
    # User A registers and gets link code
    reg_a = client.post("/auth/register", json={"email": _unique_email("link_a"), "password": "pass12345"})
    token_a = reg_a.json()["access_token"]
    code_resp = client.post("/auth/me/link_code", headers={"Authorization": f"Bearer {token_a}"})
    code = code_resp.json()["code"]
    tg_id = f"tg_409_{int(time.time() * 1000)}"
    client.post("/auth/telegram/link", json={"telegram_id": tg_id, "code": code})
    # User B registers and gets link code
    reg_b = client.post("/auth/register", json={"email": _unique_email("link_b"), "password": "pass12345"})
    token_b = reg_b.json()["access_token"]
    code_resp_b = client.post("/auth/me/link_code", headers={"Authorization": f"Bearer {token_b}"})
    code_b = code_resp_b.json()["code"]
    # Try to link same telegram_id to user B -> 409
    resp = client.post("/auth/telegram/link", json={"telegram_id": tg_id, "code": code_b})
    assert resp.status_code == 409


def test_telegram_link_already_linked_same_user(client):
    """POST /auth/telegram/link when telegram already linked to same user returns 200."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={"email": _unique_email("link_same"), "password": "pass12345"})
    token = reg.json()["access_token"]
    code_resp = client.post("/auth/me/link_code", headers={"Authorization": f"Bearer {token}"})
    code = code_resp.json()["code"]
    tg_id = f"tg_same_{int(time.time() * 1000)}"
    client.post("/auth/telegram/link", json={"telegram_id": tg_id, "code": code})
    # Call link again with same code (consumed) would fail; use new code
    code_resp2 = client.post("/auth/me/link_code", headers={"Authorization": f"Bearer {token}"})
    code2 = code_resp2.json()["code"]
    resp = client.post("/auth/telegram/link", json={"telegram_id": tg_id, "code": code2})
    assert resp.status_code == 200
    assert "already linked" in resp.json().get("message", "").lower()


def test_me_requires_auth(client):
    """GET /auth/me without Bearer returns 401."""
    _skip_if_no_db()
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_me_with_bearer(client):
    """GET /auth/me with valid token returns user."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={
        "email": _unique_email("me"),
        "password": "pass12345",
        "full_name": "Me User",
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == reg.json()["user"]["email"]
    assert me.json().get("telegram_linked") is False


def test_link_code_and_telegram_link(client):
    """Create link code with Bearer, then consume with telegram/link; me shows telegram_linked."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={
        "email": _unique_email("link"),
        "password": "pass12345",
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]

    code_resp = client.post("/auth/me/link_code", headers={"Authorization": f"Bearer {token}"})
    assert code_resp.status_code == 200
    code_data = code_resp.json()
    assert "code" in code_data
    code = code_data["code"]

    telegram_id = f"tg_{int(time.time() * 1000)}"
    link_resp = client.post("/auth/telegram/link", json={
        "telegram_id": telegram_id,
        "code": code,
    })
    assert link_resp.status_code == 200

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json().get("telegram_linked") is True
    assert me.json().get("telegram_id") == telegram_id


def test_unlink_telegram(client):
    """POST /auth/me/unlink_telegram with Bearer clears telegram_id; /auth/me shows telegram_linked false."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={
        "email": _unique_email("unlink"),
        "password": "pass12345",
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    code_resp = client.post("/auth/me/link_code", headers=headers)
    assert code_resp.status_code == 200
    code = code_resp.json()["code"]
    tg_id = f"tg_unlink_{int(time.time() * 1000)}"
    client.post("/auth/telegram/link", json={"telegram_id": tg_id, "code": code})
    me_before = client.get("/auth/me", headers=headers)
    assert me_before.json().get("telegram_linked") is True

    unlink_resp = client.post("/auth/me/unlink_telegram", headers=headers)
    assert unlink_resp.status_code == 200
    assert unlink_resp.json().get("message", "").lower().find("unlink") >= 0 or unlink_resp.json().get("status") == "ok"

    me_after = client.get("/auth/me", headers=headers)
    assert me_after.status_code == 200
    assert me_after.json().get("telegram_linked") is False
    assert me_after.json().get("telegram_id") is None


def test_telegram_link_invalid_code(client):
    """POST /auth/telegram/link with bad code returns 400."""
    _skip_if_no_db()
    resp = client.post("/auth/telegram/link", json={
        "telegram_id": "123",
        "code": "000000",
    })
    assert resp.status_code == 400


def test_refresh_token(client):
    """POST /auth/refresh with refresh_token returns new tokens."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={
        "email": _unique_email("refresh"),
        "password": "pass12345",
    })
    assert reg.status_code == 200
    refresh_token = reg.json()["refresh_token"]

    ref = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert ref.status_code == 200
    assert "access_token" in ref.json()


def test_join_with_bearer(client):
    """Join a game using Bearer token (no telegram_id)."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={
        "email": _unique_email("join"),
        "password": "pass12345",
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create = client.post("/games/create", json={"map_name": "standard"})
    assert create.status_code == 200
    game_id = int(create.json()["game_id"])

    join = client.post(
        f"/games/{game_id}/join",
        json={"game_id": game_id, "power": "FRANCE"},
        headers=headers,
    )
    assert join.status_code == 200
    assert join.json().get("status") in ("ok", "already_joined")


def test_forgot_password_and_reset(client):
    """POST /auth/forgot_password then /auth/reset_password with token allows new login."""
    _skip_if_no_db()
    email = _unique_email("forgot")
    password = "oldpass123"
    reg = client.post("/auth/register", json={"email": email, "password": password, "full_name": "Forgot User"})
    assert reg.status_code == 200

    forgot = client.post("/auth/forgot_password", json={"email": email})
    assert forgot.status_code == 200
    # In tests we don't have email; get token from db or from dev response
    # Backend doesn't return token in prod. So we need to create token via internal API or DB.
    # Alternative: have backend in test return reset_link when env DIPLOMACY_DEV_SHOW_RESET_LINK=1
    import os
    os.environ["DIPLOMACY_DEV_SHOW_RESET_LINK"] = "1"
    os.environ["DIPLOMACY_PASSWORD_RESET_BASE_URL"] = "http://localhost:5173"
    try:
        forgot2 = client.post("/auth/forgot_password", json={"email": email})
        assert forgot2.status_code == 200
        data = forgot2.json()
        reset_link = data.get("reset_link")
        assert reset_link and "token=" in reset_link
        token = reset_link.split("token=")[1].split("&")[0]
    finally:
        os.environ.pop("DIPLOMACY_DEV_SHOW_RESET_LINK", None)
        os.environ.pop("DIPLOMACY_PASSWORD_RESET_BASE_URL", None)

    reset = client.post("/auth/reset_password", json={"token": token, "new_password": "newpass123"})
    assert reset.status_code == 200

    login_old = client.post("/auth/login", json={"email": email, "password": password})
    assert login_old.status_code == 401
    login_new = client.post("/auth/login", json={"email": email, "password": "newpass123"})
    assert login_new.status_code == 200


def test_set_orders_with_bearer(client):
    """Set orders using Bearer token (no telegram_id)."""
    _skip_if_no_db()
    reg = client.post("/auth/register", json={
        "email": _unique_email("orders"),
        "password": "pass12345",
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create = client.post("/games/create", json={"map_name": "standard"})
    assert create.status_code == 200
    game_id = create.json()["game_id"]

    client.post(
        f"/games/{game_id}/join",
        json={"game_id": int(game_id), "power": "FRANCE"},
        headers=headers,
    )

    set_orders = client.post(
        "/games/set_orders",
        json={"game_id": game_id, "power": "FRANCE", "orders": ["A PAR - BUR"]},
        headers=headers,
    )
    assert set_orders.status_code == 200
