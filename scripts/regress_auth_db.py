#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import auth as auth_module
from core.auth import AuthUser, create_session_token, revoke_session_token, verify_google_id_token, verify_session_token
from core.db import connect, placeholder


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(tmp) / 'auth.sqlite'}"
        os.environ["APP_AUTH_SECRET"] = "test-auth-secret"
        os.environ["SESSION_TTL_SECONDS"] = str(60 * 60 * 24 * 14)
        os.environ["GOOGLE_CLIENT_ID"] = "client-id"

        _assert_google_token_verification()

        user = AuthUser(sub="google-sub-1", email="student@example.com", name="Student", picture="https://x.test/p.png")
        token = create_session_token(user)
        assert token.startswith("ps_as_")

        verified = verify_session_token(token)
        assert verified.sub == "google-sub-1"
        assert verified.email == "student@example.com"
        assert verified.session_id.startswith("as_")
        assert verified.session_expires_at

        p = placeholder()
        with connect() as conn:
            user_rows = conn.cursor().execute(f"SELECT * FROM users WHERE email = {p}", ["student@example.com"]).fetchall()
            session_rows = conn.cursor().execute("SELECT * FROM auth_sessions").fetchall()
        assert len(user_rows) == 1
        assert len(session_rows) == 1
        session = dict(session_rows[0])
        assert session["token_hash"] != token
        assert session["revoked_at"] is None

        assert revoke_session_token(token) == 1
        _assert_unauthorized(token, "revoked")

        second_token = create_session_token(user)
        with connect() as conn:
            active = conn.cursor().execute("SELECT token_hash FROM auth_sessions WHERE revoked_at IS NULL").fetchone()
            assert active is not None
            conn.cursor().execute(
                f"UPDATE auth_sessions SET expires_at = {p} WHERE token_hash = {p}",
                ["2000-01-01T00:00:00+00:00", dict(active)["token_hash"]],
            )
        _assert_unauthorized(second_token, "expired")

    print("PASS auth DB regression")
    return 0


def _assert_google_token_verification() -> None:
    original_urlopen = auth_module.urllib.request.urlopen

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self) -> bytes:
            return (
                b'{"aud":"client-id","email":"student@example.com",'
                b'"sub":"google-sub-1","name":"Student","picture":"https://x.test/p.png"}'
            )

    def fake_urlopen(url: str, timeout: int):
        assert "id_token=fake-token" in url
        assert timeout == 8
        return FakeResponse()

    auth_module.urllib.request.urlopen = fake_urlopen
    try:
        user = verify_google_id_token("fake-token")
    finally:
        auth_module.urllib.request.urlopen = original_urlopen
    assert user.sub == "google-sub-1"
    assert user.email == "student@example.com"
    assert user.name == "Student"


def _assert_unauthorized(token: str, expected: str) -> None:
    try:
        verify_session_token(token)
    except HTTPException as exc:
        assert exc.status_code == 401
        assert expected in str(exc.detail).lower()
        return
    raise AssertionError(f"expected token to be rejected as {expected}")


if __name__ == "__main__":
    raise SystemExit(main())
