"""開発用モックトークン検証"""

from typing import Any

from app.auth.exceptions import MockTokenError


def verify_mock_token(token: str) -> dict[str, Any]:
    """形式 'mock:<firebase_uid>:<email>' をパースして dict 返却。

    形式不正時は MockTokenError を投げる。
    Firebase verify_id_token 互換の payload 形式を返す。
    """
    if not token.startswith("mock:"):
        raise MockTokenError("Mock token must start with 'mock:'")

    parts = token.split(":", 2)
    if len(parts) != 3:
        raise MockTokenError("Mock token format must be 'mock:<uid>:<email>'")

    _, uid, email = parts
    if not uid or not email:
        raise MockTokenError("Mock token uid and email must be non-empty")

    return {
        "uid": uid,
        "email": email,
        "email_verified": True,
        "name": None,
        "firebase": {"sign_in_provider": "mock"},
    }
