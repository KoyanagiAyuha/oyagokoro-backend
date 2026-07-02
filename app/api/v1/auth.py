"""auth API エンドポイント"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_firebase_payload
from app.database import get_session
from app.models.user import User
from app.schemas import UserCreateRequest, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="初回同期（冪等UPSERT）",
)
async def register(
    body: UserCreateRequest,
    payload: dict = Depends(get_current_firebase_payload),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Firebase ID Token から firebase_uid と email を取り出して User を冪等 upsert。

    PostgreSQL の ON CONFLICT を用いた1クエリ UPSERT で race condition を解消。
    既存ユーザーがいればそのまま返す（display_name 等は body で上書きしない）。
    """
    firebase_uid = payload["uid"]
    email = payload.get("email")

    # MAJ-E-1 防御: email が取得できないトークンは 400 で拒否
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_INVALID_TOKEN",
                "message": "Token payload missing email",
            },
        )

    # ON CONFLICT で冪等 UPSERT。既存行は firebase_uid のみ再代入（実質 no-op）し
    # RETURNING で取得する。DO NOTHING だと既存時に RETURNING が空になるため DO UPDATE 方式を採用。
    stmt = (
        pg_insert(User)
        .values(
            firebase_uid=firebase_uid,
            email=email,
            display_name=body.display_name,
            locale=body.locale,
            timezone=body.timezone,
        )
        .on_conflict_do_update(
            index_elements=["firebase_uid"],
            set_={"firebase_uid": firebase_uid},  # no-op だが RETURNING を返すため必要
        )
        .returning(User)
    )
    result = await session.execute(stmt)
    await session.commit()
    user = result.scalar_one()
    return user
