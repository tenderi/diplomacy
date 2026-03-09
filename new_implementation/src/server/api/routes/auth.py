"""
Auth routes: register, login, refresh, me, link_code, link_telegram.

Uses JWT (PyJWT) for access/refresh tokens and bcrypt for passwords.
Password reset emails can be sent via SMTP when DIPLOMACY_SMTP_* env vars are set.
"""
import logging
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator

from ..shared import db_service

# Password hashing: use bcrypt directly (avoids passlib/bcrypt version quirks)
try:
    import bcrypt
    _bcrypt_available = True
except ImportError:  # pragma: no cover
    _bcrypt_available = False

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT config from env (min 32 bytes for HS256 per RFC 7518)
JWT_SECRET = os.environ.get("DIPLOMACY_JWT_SECRET", "dev-secret-change-in-production-32b")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Optional Bearer (for routes that support both Bearer and body telegram_id)
http_bearer = HTTPBearer(auto_error=False)


# --- Request/Response models ---
class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.strip().lower() if v else v

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.strip().lower() if v else v


class RefreshRequest(BaseModel):
    refresh_token: str


class LinkTelegramRequest(BaseModel):
    telegram_id: str
    code: str


class ForgotPasswordRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.strip().lower() if v else v


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


# --- Helpers ---
def _hash_password(password: str) -> str:
    if not _bcrypt_available:
        raise HTTPException(status_code=500, detail="Password hashing not available (install bcrypt)")
    raw = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(raw, bcrypt.gensalt())
    return hashed.decode("ascii")


def _verify_password(plain: str, hashed: str) -> bool:
    if not _bcrypt_available:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except Exception:
        return False


def _create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _create_refresh_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": str(user_id), "exp": expire, "type": "refresh"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str, expected_type: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") != expected_type:
            return None
        return int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, KeyError):
        return None


# --- Dependencies ---
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Any:
    """Require valid Bearer access token; return user model or raise 401."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = credentials.credentials
    user_id = _decode_token(token, "access")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db_service.get_user_by_id(user_id)
    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> Optional[Any]:
    """If Bearer token present and valid, return user; else return None. Used with telegram_id fallback."""
    if not credentials:
        return None
    token = credentials.credentials
    user_id = _decode_token(token, "access")
    if user_id is None:
        return None
    user = db_service.get_user_by_id(user_id)
    if not user or not getattr(user, "is_active", True):
        return None
    return user


def resolve_user_or_telegram(
    credentials: Optional[HTTPAuthorizationCredentials],
    telegram_id: Optional[str],
) -> Any:
    """Resolve to user from Bearer token or from telegram_id. Raises 401 if neither works."""
    user = None
    if credentials:
        user_id = _decode_token(credentials.credentials, "access")
        if user_id is not None:
            user = db_service.get_user_by_id(user_id)
    if user is None and telegram_id:
        user = db_service.get_user_by_telegram_id(telegram_id)
    if user is None or not getattr(user, "is_active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def _user_response(user: Any) -> Dict[str, Any]:
    return {
        "id": user.id,
        "email": getattr(user, "email", None),
        "full_name": getattr(user, "full_name", None),
        "telegram_id": getattr(user, "telegram_id", None),
        "telegram_linked": getattr(user, "telegram_id", None) is not None and str(user.telegram_id).strip() != "",
    }


# --- Routes ---
@router.post("/register")
def register(req: RegisterRequest) -> Dict[str, Any]:
    """Register with email and password. Returns user and tokens."""
    if not _bcrypt_available:
        raise HTTPException(status_code=500, detail="Auth not configured (bcrypt)")
    email = req.email.strip().lower()
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    existing = db_service.get_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    password_hash = _hash_password(req.password)
    user = db_service.create_user_with_password(
        email=email,
        password_hash=password_hash,
        full_name=req.full_name,
    )
    access = _create_access_token(user.id)
    refresh = _create_refresh_token(user.id)
    return {
        "user": _user_response(user),
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/login")
def login(req: LoginRequest) -> Dict[str, Any]:
    """Login with email and password. Returns user and tokens."""
    user = db_service.get_user_by_email(req.email)
    if not user or not getattr(user, "password_hash", None):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not _verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not getattr(user, "is_active", True):
        raise HTTPException(status_code=401, detail="Account inactive")
    access = _create_access_token(user.id)
    refresh = _create_refresh_token(user.id)
    return {
        "user": _user_response(user),
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/token")
def token(form: OAuth2PasswordRequestForm = Depends()) -> Dict[str, Any]:
    """OAuth2 compatible token endpoint (username=email, password). For Swagger Authorize."""
    user = db_service.get_user_by_email(form.username)
    if not user or not getattr(user, "password_hash", None):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not _verify_password(form.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access = _create_access_token(user.id)
    refresh = _create_refresh_token(user.id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
    }


@router.post("/refresh")
def refresh(req: RefreshRequest) -> Dict[str, Any]:
    """Exchange refresh token for new access (and refresh) token."""
    user_id = _decode_token(req.refresh_token, "refresh")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db_service.get_user_by_id(user_id)
    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status_code=401, detail="User not found or inactive")
    access = _create_access_token(user.id)
    new_refresh = _create_refresh_token(user.id)
    return {
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.get("/me")
def me(current_user: Any = Depends(get_current_user)) -> Dict[str, Any]:
    """Return current user (requires Bearer token)."""
    return _user_response(current_user)


@router.post("/me/link_code")
def create_link_code(
    current_user: Any = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a one-time code to link Telegram to this account. Code valid for 10 minutes."""
    ttl_minutes = 10
    code, expires_at = db_service.create_link_code(current_user.id, ttl_minutes=ttl_minutes)
    return {
        "code": code,
        "expires_in_seconds": ttl_minutes * 60,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/me/unlink_telegram")
def unlink_telegram(current_user: Any = Depends(get_current_user)) -> Dict[str, Any]:
    """Unlink Telegram from the current account (requires Bearer token)."""
    if not getattr(current_user, "telegram_id", None):
        return {"status": "ok", "message": "No Telegram linked."}
    db_service.unlink_telegram(current_user.id)
    return {"status": "ok", "message": "Telegram unlinked."}


# Forgot password: TTL for reset token (minutes)
PASSWORD_RESET_TTL_MINUTES = 60

_logger = logging.getLogger("diplomacy.server.api.auth")

# SMTP env vars (optional): DIPLOMACY_SMTP_HOST, DIPLOMACY_SMTP_PORT, DIPLOMACY_SMTP_USER,
# DIPLOMACY_SMTP_PASSWORD, DIPLOMACY_SMTP_FROM, DIPLOMACY_SMTP_USE_TLS


def _send_password_reset_link(email: str, reset_link: str) -> None:
    """Send reset link by email if SMTP is configured (DIPLOMACY_SMTP_HOST), otherwise log only."""
    smtp_host = os.environ.get("DIPLOMACY_SMTP_HOST", "").strip()
    if smtp_host:
        try:
            _send_password_reset_email_smtp(email, reset_link, smtp_host)
            _logger.info("Password reset email sent to %s via SMTP", email)
            return
        except Exception as e:  # noqa: BLE001
            _logger.warning("Failed to send password reset email to %s: %s", email, e)
    if os.environ.get("DIPLOMACY_DEV_SHOW_RESET_LINK"):
        _logger.info("Password reset link for %s: %s", email, reset_link)
    else:
        _logger.info(
            "Password reset requested for %s (link not logged; set DIPLOMACY_DEV_SHOW_RESET_LINK=1 for dev)",
            email,
        )


def _send_password_reset_email_smtp(recipient: str, reset_link: str, host: str) -> None:
    """Send a single password-reset email via SMTP. Raises on failure."""
    port = int(os.environ.get("DIPLOMACY_SMTP_PORT", "587"))
    use_tls = os.environ.get("DIPLOMACY_SMTP_USE_TLS", "1").strip().lower() in ("1", "true", "yes")
    user = os.environ.get("DIPLOMACY_SMTP_USER", "").strip()
    password = os.environ.get("DIPLOMACY_SMTP_PASSWORD", "").strip()
    from_addr = os.environ.get("DIPLOMACY_SMTP_FROM", user or "noreply@diplomacy").strip()
    from_name = os.environ.get("DIPLOMACY_SMTP_FROM_NAME", "Diplomacy").strip()

    subject = "Password reset - Diplomacy"
    body = f"""You requested a password reset. Use this link to set a new password (valid for 1 hour):\n\n{reset_link}\n\nIf you did not request this, you can ignore this email."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, from_addr))
    msg["To"] = recipient

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(from_addr, [recipient], msg.as_string())


@router.post("/forgot_password")
def forgot_password(req: ForgotPasswordRequest) -> Dict[str, Any]:
    """Request a password reset. Always returns 200 to avoid email enumeration.
    If DIPLOMACY_SMTP_HOST is set, sends the reset link by email; otherwise only logs.
    Set DIPLOMACY_PASSWORD_RESET_BASE_URL for the link URL; DIPLOMACY_DEV_SHOW_RESET_LINK=1 returns the link in the response for dev."""
    email = req.email.strip().lower()
    out: Dict[str, Any] = {"message": "If an account exists with this email, you will receive a reset link."}
    if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        return out
    user = db_service.get_user_by_email(email)
    if user and getattr(user, "password_hash", None):
        token = db_service.create_password_reset_token(user.id, ttl_minutes=PASSWORD_RESET_TTL_MINUTES)
        base_url = os.environ.get("DIPLOMACY_PASSWORD_RESET_BASE_URL", "").rstrip("/")
        if base_url:
            reset_link = f"{base_url}/reset-password?token={token}"
            _send_password_reset_link(email, reset_link)
            if os.environ.get("DIPLOMACY_DEV_SHOW_RESET_LINK"):
                out["reset_link"] = reset_link  # For dev/frontend to show link when email not configured
    return out


@router.post("/reset_password")
def reset_password(req: ResetPasswordRequest) -> Dict[str, Any]:
    """Set new password using a reset token (from forgot_password flow). Token is single-use and expires after PASSWORD_RESET_TTL_MINUTES (default 60)."""
    if not _bcrypt_available:
        raise HTTPException(status_code=500, detail="Password reset not available (install bcrypt)")
    user_id = db_service.consume_password_reset_token(req.token)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    password_hash = _hash_password(req.new_password)
    db_service.set_user_password(user_id, password_hash)
    return {"message": "Password has been reset. You can now log in."}


@router.post("/telegram/link")
def link_telegram(req: LinkTelegramRequest) -> Dict[str, Any]:
    """Link Telegram to an account using a code (called by Telegram bot when user sends /link <code>). No JWT."""
    user_id = db_service.consume_link_code(req.code)
    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid or expired code")
    existing = db_service.get_user_by_telegram_id(req.telegram_id)
    if existing and existing.id != user_id:
        raise HTTPException(status_code=409, detail="This Telegram is already linked to another account")
    if existing and existing.id == user_id:
        return {"status": "ok", "message": "Telegram already linked to your account."}
    db_service.set_user_telegram_id(user_id, req.telegram_id)
    return {"status": "ok", "message": "Telegram linked to your account."}
