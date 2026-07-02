"""users API エンドポイント"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.user import User
from app.schemas import UserRead, UserTermsAgreeRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="ログイン中ユーザー情報を取得",
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """認証済みユーザーの情報を返す。terms_agreed_at=NULL のままでも 200 で返す。"""
    return current_user


@router.post(
    "/me/terms-agreement",
    response_model=UserRead,
    summary="利用規約に同意",
)
async def agree_terms(
    body: UserTermsAgreeRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    """terms_agreed_at と terms_version を同時更新する。

    CHECK 制約 users_terms_both_or_none を満たすため両カラム同時 SET。
    updated_at もアプリ層で明示更新（モデルに UPDATE トリガ未定義のため）。
    冪等性: 既に同意済みのユーザーが再度 POST しても terms_agreed_at を最新時刻に
    更新する（バージョン更新時の再同意に有用）。
    """
    stmt = (
        update(User)
        .where(User.id == current_user.id)
        .values(
            terms_agreed_at=func.now(),
            terms_version=body.terms_version,
            updated_at=func.now(),
        )
    )
    await session.execute(stmt)
    await session.commit()
    await session.refresh(current_user)
    return current_user
