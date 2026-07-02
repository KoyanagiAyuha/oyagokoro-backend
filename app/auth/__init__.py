"""認証エントリポイント"""

from typing import Any

from app.auth.exceptions import (
    FirebaseNotConfiguredError,
    InvalidTokenError,
    MockTokenError,
)
from app.auth.firebase import verify_id_token
from app.auth.mock import verify_mock_token
from app.settings import settings


def verify_id_token_or_mock(token: str) -> dict[str, Any]:
    """トークン検証ディスパッチャ。

    USE_AUTH_MOCK=true かつ APP_ENV != 'production' のときのみモック検証。
    本番環境では多重防御として常に実トークン検証。
    """
    if settings.use_auth_mock and settings.app_env != "production":
        return verify_mock_token(token)
    return verify_id_token(token)


__all__ = [
    "FirebaseNotConfiguredError",
    "InvalidTokenError",
    "MockTokenError",
    "verify_id_token",
    "verify_id_token_or_mock",
    "verify_mock_token",
]
