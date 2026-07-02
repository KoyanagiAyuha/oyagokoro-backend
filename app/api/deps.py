"""FastAPI 共通の Depends 関数"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import verify_id_token_or_mock
from app.auth.exceptions import (
    FirebaseNotConfiguredError,
    InvalidTokenError,
    MockTokenError,
)
from app.database import get_session
from app.models.user import User

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_firebase_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict:
    """Bearer Token を抽出 → verify → payload dict 返却。

    失敗時は 401 を返す。
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_MISSING_TOKEN", "message": "Bearer token required"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return verify_id_token_or_mock(credentials.credentials)
    except (InvalidTokenError, MockTokenError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": str(e)},
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except FirebaseNotConfiguredError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "ERR_AUTH_NOT_CONFIGURED", "message": str(e)},
        ) from e


async def get_current_user(
    payload: dict = Depends(get_current_firebase_payload),
    session: AsyncSession = Depends(get_session),
) -> User:
    """payload の firebase_uid で users を検索。

    見つからなければ 404 ERR_USER_NOT_FOUND。
    """
    firebase_uid = payload.get("uid")
    if not firebase_uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "ERR_INVALID_TOKEN", "message": "Token payload missing uid"},
        )

    result = await session.execute(select(User).where(User.firebase_uid == firebase_uid))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ERR_USER_NOT_FOUND",
                "message": "User not registered. POST /api/v1/auth/register to create.",
            },
        )
    return user
