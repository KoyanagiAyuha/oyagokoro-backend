"""Firebase Admin SDK の遅延初期化と ID Token 検証"""

from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth as fb_auth
from firebase_admin import credentials

from app.auth.exceptions import FirebaseNotConfiguredError, InvalidTokenError
from app.settings import settings

_app: firebase_admin.App | None = None


def _build_credentials() -> credentials.Base:
    """Settings から credentials を構築。優先順位: ファイル参照 > 3変数式"""
    if settings.firebase_credentials_file:
        path = Path(settings.firebase_credentials_file)
        if path.exists():
            return credentials.Certificate(str(path))

    if settings.firebase_project_id and settings.firebase_private_key and settings.firebase_client_email:
        return credentials.Certificate(
            {
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "private_key": settings.firebase_private_key.replace("\\n", "\n"),
                "client_email": settings.firebase_client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )

    raise FirebaseNotConfiguredError(
        "Firebase credentials not configured. "
        "Set FIREBASE_CREDENTIALS_FILE or all of FIREBASE_PROJECT_ID/PRIVATE_KEY/CLIENT_EMAIL."
    )


def _get_app() -> firebase_admin.App:
    """Firebase Admin App の遅延初期化（シングルトン）"""
    global _app
    if _app is None:
        cred = _build_credentials()
        _app = firebase_admin.initialize_app(cred)
    return _app


def verify_id_token(token: str) -> dict[str, Any]:
    """Firebase ID Token を検証して payload を返す。

    失敗時は InvalidTokenError を投げる。
    """
    app = _get_app()
    try:
        return fb_auth.verify_id_token(token, app=app)
    except Exception as e:
        raise InvalidTokenError(f"Invalid Firebase ID Token: {e}") from e
