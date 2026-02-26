"""
Auth routes: register, login, refresh, me, link_code, link_telegram.

Uses JWT (PyJWT) for access/refresh tokens and passlib+bcrypt for passwords.
"""
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, field_validator

from ..shared import db_service

# Password hashing
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
except ImportError:
    pwd_context = None  # type: ignore

router = APIRouter(prefix="/auth", tags=["auth"])

# JWT config from env
JWT_SECRET = os.environ.get("DIPLOMACY_JWT_SECRET", "dev-secret-change-in-production")
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


# --- Helpers ---
def _hash_password(password: str) -> str:
    if not pwd_context:
        raise HTTPException(status_code=500, detail="Password hashing not available (install passlib[bcrypt])")
    return pwd_context.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    if not pwd_context:
        return False
    return pwd_context.verify(plain, hashed)


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
    if not pwd_context:
        raise HTTPException(status_code=500, detail="Auth not configured (passlib)")
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
