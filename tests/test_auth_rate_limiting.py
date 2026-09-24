"""
Tests for C2: brute-force / rate-limiting protection on password auth.

Covers /auth/login, /auth/token, and /auth/register. The limiter itself lives
in server.api.routes.auth (_rate_limit_attempts / _check_rate_limit /
_record_attempt); these tests hit it only through the HTTP surface via
TestClient, and monkeypatch server.api.routes.auth.time.time for the
window-reset test rather than sleeping for real.
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


def _skip_if_no_db():
    if not _get_db_url():
        pytest.skip("Database URL not configured (SQLALCHEMY_DATABASE_URL)")


def _unique_email(prefix="ratelimit"):
    return f"{prefix}_{int(time.time() * 1000)}_{os.getpid()}@example.com"


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from server.api import app
    return TestClient(app)


def _client_with_ip(ip: str):
    """A TestClient whose ASGI scope reports a distinct client IP, so tests
    can exercise the per-IP bucket independently of the per-email bucket."""
    from fastapi.testclient import TestClient
    from server.api import app
    return TestClient(app, client=(ip, 12345))


@pytest.fixture(autouse=True)
def _reset_limiter():
    """Belt-and-suspenders: the global autouse fixture in conftest.py already
    resets between tests, but resetting again here makes this file order
    independent even if run in isolation."""
    from server.api.routes.auth import reset_rate_limits
    reset_rate_limits()
    yield
    reset_rate_limits()


# --- /auth/login ---

def test_login_bad_password_hammered_past_threshold_returns_429_with_retry_after(client):
    """Repeated wrong-password attempts against one email trip the per-email
    bucket (threshold 5 / 15 min) with 429 + a real Retry-After header."""
    _skip_if_no_db()
    from server.api.routes.auth import _LOGIN_EMAIL_RATE_LIMIT_MAX

    email = _unique_email("badpw")
    reg = client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})
    assert reg.status_code == 200

    last = None
    for _ in range(_LOGIN_EMAIL_RATE_LIMIT_MAX):
        last = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert last.status_code == 401

    resp = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) > 0


def test_login_bucket_isolation_other_account_and_ip_still_succeeds(client):
    """A locked-out email/IP does not block a *different* account logging in
    correctly from a different IP."""
    _skip_if_no_db()
    from server.api.routes.auth import _LOGIN_EMAIL_RATE_LIMIT_MAX

    locked_client = _client_with_ip("10.0.0.1")
    locked_email = _unique_email("locked")
    reg = locked_client.post(
        "/auth/register", json={"email": locked_email, "password": "correct-horse-1"}
    )
    assert reg.status_code == 200
    for _ in range(_LOGIN_EMAIL_RATE_LIMIT_MAX):
        resp = locked_client.post(
            "/auth/login", json={"email": locked_email, "password": "wrong-password"}
        )
        assert resp.status_code == 401

    # Confirm the locked account is indeed locked now.
    locked_resp = locked_client.post(
        "/auth/login", json={"email": locked_email, "password": "wrong-password"}
    )
    assert locked_resp.status_code == 429

    # A different account, different password, correct credentials, different
    # IP -- still succeeds (per-email and per-IP buckets are independent).
    other_client = _client_with_ip("10.0.0.2")
    other_email = _unique_email("other")
    other_password = "another-correct-1"
    reg2 = other_client.post(
        "/auth/register", json={"email": other_email, "password": other_password}
    )
    assert reg2.status_code == 200
    ok = other_client.post("/auth/login", json={"email": other_email, "password": other_password})
    assert ok.status_code == 200
    assert ok.json()["user"]["email"] == other_email


def test_login_limiter_resets_after_window_via_fake_clock(client, monkeypatch):
    """After the window rolls over, a previously-locked email can log in
    again -- no permanent lockout. Uses a monkeypatched clock, not sleep."""
    _skip_if_no_db()
    import server.api.routes.auth as auth_module

    email = _unique_email("windowreset")
    password = "correct-horse-1"
    reg = client.post("/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 200

    fake_now = [time.time()]
    monkeypatch.setattr(auth_module.time, "time", lambda: fake_now[0])

    for _ in range(auth_module._LOGIN_EMAIL_RATE_LIMIT_MAX):
        resp = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
        assert resp.status_code == 401

    blocked = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert blocked.status_code == 429

    # Advance the fake clock past the window.
    fake_now[0] += auth_module._LOGIN_EMAIL_RATE_LIMIT_WINDOW + 1

    # No permanent lockout: the legitimate user can log in again once the
    # window has rolled over.
    recovered = client.post("/auth/login", json={"email": email, "password": password})
    assert recovered.status_code == 200


def test_login_unknown_email_counts_against_same_bucket_as_wrong_password(client):
    """An unknown email must not get a separate/free counter -- it shares the
    per-email bucket with a real wrong-password attempt on that address."""
    _skip_if_no_db()
    from server.api.routes.auth import _LOGIN_EMAIL_RATE_LIMIT_MAX

    unknown_email = _unique_email("unknown")

    # Fill the bucket with attempts against the *unknown* email.
    for _ in range(_LOGIN_EMAIL_RATE_LIMIT_MAX):
        resp = client.post("/auth/login", json={"email": unknown_email, "password": "whatever"})
        assert resp.status_code == 401

    # Now register that exact email with a real password -- if unknown-email
    # attempts hadn't counted against the bucket, this next attempt would be
    # under threshold; because they share a bucket, it's still blocked.
    client.post("/auth/register", json={"email": unknown_email, "password": "correct-horse-1"})
    resp = client.post("/auth/login", json={"email": unknown_email, "password": "still-wrong"})
    assert resp.status_code == 429


def test_login_success_does_not_burn_failure_budget(client):
    """Repeated *successful* logins must never trip the limiter -- otherwise
    normal use (and the rest of the test suite) would start 429ing."""
    _skip_if_no_db()
    from server.api.routes.auth import _LOGIN_EMAIL_RATE_LIMIT_MAX

    email = _unique_email("goodlogin")
    password = "correct-horse-1"
    client.post("/auth/register", json={"email": email, "password": password})

    for _ in range(_LOGIN_EMAIL_RATE_LIMIT_MAX * 2):
        resp = client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200


# --- /auth/token ---

def test_token_endpoint_hammered_past_threshold_returns_429(client):
    """/auth/token shares the login buckets: hammering it with a wrong
    password also trips 429 + Retry-After."""
    _skip_if_no_db()
    from server.api.routes.auth import _LOGIN_EMAIL_RATE_LIMIT_MAX

    email = _unique_email("token429")
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})

    for _ in range(_LOGIN_EMAIL_RATE_LIMIT_MAX):
        resp = client.post(
            "/auth/token",
            data={"username": email, "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    resp = client.post(
        "/auth/token",
        data={"username": email, "password": "wrong"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_token_and_login_share_the_same_bucket(client):
    """An attacker cannot dodge the /auth/login limiter by switching to
    /auth/token for the same email -- failures on one endpoint count against
    the other."""
    _skip_if_no_db()
    from server.api.routes.auth import _LOGIN_EMAIL_RATE_LIMIT_MAX

    email = _unique_email("shared")
    client.post("/auth/register", json={"email": email, "password": "correct-horse-1"})

    # Split failures across both endpoints.
    half = _LOGIN_EMAIL_RATE_LIMIT_MAX // 2
    for _ in range(half):
        resp = client.post("/auth/login", json={"email": email, "password": "wrong"})
        assert resp.status_code == 401
    for _ in range(_LOGIN_EMAIL_RATE_LIMIT_MAX - half):
        resp = client.post(
            "/auth/token",
            data={"username": email, "password": "wrong"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code == 401

    # Bucket should now be tripped, regardless of which endpoint is hit next.
    final = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert final.status_code == 429


# --- /auth/register ---

def test_register_hammered_past_threshold_returns_429(client, monkeypatch):
    """A coarser per-IP-only limit applies to /auth/register (account-creation
    spam). Lower the threshold via monkeypatch so the test doesn't need to
    make 20+ requests."""
    _skip_if_no_db()
    import server.api.routes.auth as auth_module

    monkeypatch.setattr(auth_module, "_REGISTER_IP_RATE_LIMIT_MAX", 3)

    last = None
    for _ in range(3):
        last = client.post(
            "/auth/register",
            json={"email": _unique_email("regspam"), "password": "pass12345"},
        )
        assert last.status_code == 200

    resp = client.post(
        "/auth/register",
        json={"email": _unique_email("regspam"), "password": "pass12345"},
    )
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_register_limit_is_per_ip_not_per_email(client, monkeypatch):
    """Register rate limiting has no per-email keying -- distinct emails from
    the same (test-client) IP still share one bucket."""
    _skip_if_no_db()
    import server.api.routes.auth as auth_module

    monkeypatch.setattr(auth_module, "_REGISTER_IP_RATE_LIMIT_MAX", 2)

    r1 = client.post(
        "/auth/register", json={"email": _unique_email("a"), "password": "pass12345"}
    )
    r2 = client.post(
        "/auth/register", json={"email": _unique_email("b"), "password": "pass12345"}
    )
    assert r1.status_code == 200
    assert r2.status_code == 200

    r3 = client.post(
        "/auth/register", json={"email": _unique_email("c"), "password": "pass12345"}
    )
    assert r3.status_code == 429


# --- Unbounded memory growth (driver review follow-up) ---

def test_rate_limit_dict_does_not_accumulate_dead_keys(client, monkeypatch):
    """Regression test for the unbounded-memory-growth defect flagged in
    driver review: `_check_rate_limit` used to read via a `defaultdict`,
    which creates a permanent dict entry as a side effect of merely *reading*
    a key -- even when nothing is ever recorded against it (e.g. every
    successful login checks both buckets but records neither). Separately,
    purging expired timestamps from a bucket used to leave an empty `[]`
    behind in the dict forever instead of deleting the key.

    Asserts directly on `len(server.api.routes.auth._rate_limit_attempts)` --
    a test that only checks 429 behavior would pass without either fix and
    prove nothing about memory growth.
    """
    _skip_if_no_db()
    import server.api.routes.auth as auth_module

    # Registering 26 accounts in this test would otherwise trip the (unrelated)
    # per-IP register limiter; raise it so it can't interfere with what this
    # test actually checks (the login_* buckets).
    monkeypatch.setattr(auth_module, "_REGISTER_IP_RATE_LIMIT_MAX", 1000)

    fake_now = [time.time()]
    monkeypatch.setattr(auth_module.time, "time", lambda: fake_now[0])

    def _login_buckets():
        return {
            k: v for k, v in auth_module._rate_limit_attempts.items() if k.startswith("login_")
        }

    # Part 1: many distinct *successful* logins only ever check the login_ip
    # and login_email buckets -- they never record. None of them may leave a
    # dict entry behind (the pre-fix defaultdict read would create one empty
    # list per distinct email, unboundedly, for as long as the process runs).
    for i in range(25):
        email = _unique_email(f"leak_ok_{i}")
        password = "correct-horse-1"
        reg = client.post("/auth/register", json={"email": email, "password": password})
        assert reg.status_code == 200
        ok = client.post("/auth/login", json={"email": email, "password": password})
        assert ok.status_code == 200
    assert _login_buckets() == {}, (
        "successful logins must not create permanent rate-limit dict entries"
    )

    # Part 2: a bucket that later fully expires and is re-checked must be
    # reclaimed (its key deleted), not left behind as an empty list forever.
    email = _unique_email("leak_expired")
    password = "correct-horse-1"
    client.post("/auth/register", json={"email": email, "password": password})
    for _ in range(auth_module._LOGIN_EMAIL_RATE_LIMIT_MAX):
        resp = client.post("/auth/login", json={"email": email, "password": "wrong"})
        assert resp.status_code == 401
    assert f"login_email:{email}" in auth_module._rate_limit_attempts
    assert len(_login_buckets()) == 2  # login_email:... + login_ip:...

    fake_now[0] += auth_module._LOGIN_EMAIL_RATE_LIMIT_WINDOW + 1

    ok2 = client.post("/auth/login", json={"email": email, "password": password})
    assert ok2.status_code == 200
    assert f"login_email:{email}" not in auth_module._rate_limit_attempts, (
        "an expired bucket must be deleted from the dict when re-checked, not left as []"
    )
    assert _login_buckets() == {}
