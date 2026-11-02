"""The suite hashes passwords at bcrypt's minimum cost (tests/conftest.py patches
``bcrypt.gensalt``) to keep it fast. This checks that the patch is test-only:
with the real ``gensalt``, the API hashes at bcrypt's default cost of 12."""

import bcrypt
import pytest

from server.api.routes import auth as auth_routes
from tests.conftest import REAL_BCRYPT_GENSALT


def test_the_suite_hashes_at_the_minimum_cost() -> None:
    assert auth_routes._hash_password("correct horse").startswith("$2b$04$")


def test_production_hashes_at_bcrypts_default_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bcrypt, "gensalt", REAL_BCRYPT_GENSALT)
    hashed = auth_routes._hash_password("correct horse")
    assert hashed.startswith("$2b$12$")
    assert auth_routes._verify_password("correct horse", hashed) is True
