"""capsules API エンドポイント"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_session
from app.models.capsule import Capsule
from app.models.capsule_member import CapsuleMember
from app.models.user import User
from app.schemas import CapsuleCreateRequest, CapsuleListResponse, CapsuleOpenDateUpdateRequest, CapsuleRead
from app.schemas.capsule import CapsuleMembershipRead

router = APIRouter(prefix="/capsules", tags=["capsules"])


def _is_in_past(value: datetime) -> bool:
    """value が現在時刻以前かどうかを判定する。

    value がタイムゾーン情報を持たない場合は UTC とみなして比較する
    （naive/aware 混在比較による TypeError を避けるため）。
    """
    now = datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= now


async def _build_capsule_read(session: AsyncSession, capsule: Capsule, current_user_id: UUID) -> CapsuleRead:
    """Capsule 行から CapsuleRead を組み立てるヘルパ。

    - member_count: 当該カプセルの status='active' の capsule_members 件数
    - is_frozen: active 参加者 0 人の凍結状態
    - my_membership: 呼び出しユーザーの capsule_members 行（member_id / status）。無ければ None
    """
    count_result = await session.execute(
        select(func.count())
        .select_from(CapsuleMember)
        .where(CapsuleMember.capsule_id == capsule.id, CapsuleMember.status == "active")
    )
    member_count = count_result.scalar_one()

    membership_result = await session.execute(
        select(CapsuleMember)
        .where(CapsuleMember.capsule_id == capsule.id, CapsuleMember.user_id == current_user_id)
        .order_by(CapsuleMember.created_at.desc())
    )
    membership = membership_result.scalars().first()
    my_membership = (
        CapsuleMembershipRead(member_id=membership.id, status=membership.status) if membership is not None else None
    )

    return CapsuleRead(
        id=capsule.id,
        name=capsule.name,
        open_at=capsule.open_at,
        unsealed_at=capsule.unsealed_at,
        unseal_trigger=capsule.unseal_trigger,
        is_frozen=member_count == 0,
        created_by=capsule.created_by,
        member_count=member_count,
        my_membership=my_membership,
        created_at=capsule.created_at,
        updated_at=capsule.updated_at,
    )


async def _get_capsule_or_404(session: AsyncSession, capsule_id: UUID) -> Capsule:
    """capsule_id でカプセルを取得する。存在しなければ 404 ERR_CAPSULE_NOT_FOUND。"""
    result = await session.execute(select(Capsule).where(Capsule.id == capsule_id))
    capsule = result.scalar_one_or_none()
    if capsule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CAPSULE_NOT_FOUND", "message": "カプセルが見つかりません"},
        )
    return capsule


async def _require_active_membership(session: AsyncSession, capsule_id: UUID, user_id: UUID) -> None:
    """対象カプセルの active 参加者であることを検証する。非参加者は 403 ERR_NOT_CAPSULE_MEMBER。"""
    result = await session.execute(
        select(CapsuleMember).where(
            CapsuleMember.capsule_id == capsule_id,
            CapsuleMember.user_id == user_id,
            CapsuleMember.status == "active",
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_NOT_CAPSULE_MEMBER", "message": "このカプセルの参加者ではありません"},
        )


@router.post(
    "",
    response_model=CapsuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="カプセル作成",
)
async def create_capsule(
    body: CapsuleCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CapsuleRead:
    """タイムカプセルを新規作成する。作成者は自動的に active 参加者になる（api-spec §3.1）。

    認可: 認証済み かつ terms_agreed_at 非 NULL 必須（未同意は 403 ERR_TERMS_NOT_AGREED）。
    capsules 行と作成者の capsule_members 行を 1 トランザクションで INSERT する。
    """
    if current_user.terms_agreed_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ERR_TERMS_NOT_AGREED", "message": "利用規約への同意が必要です"},
        )
    if _is_in_past(body.open_at):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_OPEN_AT_IN_PAST", "message": "open_at は未来日時を指定してください"},
        )

    capsule = Capsule(name=body.name, open_at=body.open_at, created_by=current_user.id)
    session.add(capsule)
    await session.flush()  # capsule.id を確定させ capsule_members から参照できるようにする

    member = CapsuleMember(
        capsule_id=capsule.id,
        user_id=current_user.id,
        invited_email=current_user.email,
        status="active",
        joined_at=func.now(),
    )
    session.add(member)
    await session.commit()
    await session.refresh(capsule)

    return await _build_capsule_read(session, capsule, current_user.id)


@router.get(
    "",
    response_model=CapsuleListResponse,
    summary="自分の参加カプセル一覧",
)
async def list_capsules(
    state: Literal["sealed", "unsealed", "all"] = Query(default="all"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CapsuleListResponse:
    """呼び出しユーザーが active 参加しているカプセル一覧を返す（api-spec §3.2）。

    state=sealed は unsealed_at IS NULL、state=unsealed は unsealed_at IS NOT NULL で絞り込む。
    """
    stmt = (
        select(Capsule)
        .join(CapsuleMember, CapsuleMember.capsule_id == Capsule.id)
        .where(CapsuleMember.user_id == current_user.id, CapsuleMember.status == "active")
        .order_by(Capsule.created_at.desc())
    )
    if state == "sealed":
        stmt = stmt.where(Capsule.unsealed_at.is_(None))
    elif state == "unsealed":
        stmt = stmt.where(Capsule.unsealed_at.is_not(None))

    result = await session.execute(stmt)
    capsules = result.scalars().all()
    items = [await _build_capsule_read(session, capsule, current_user.id) for capsule in capsules]
    return CapsuleListResponse(items=items, total=len(items))


@router.get(
    "/{capsule_id}",
    response_model=CapsuleRead,
    summary="カプセル詳細",
)
async def get_capsule(
    capsule_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CapsuleRead:
    """カプセル詳細を返す（api-spec §3.3）。

    認可: 対象カプセルの active 参加者のみ。非参加者・非存在はいずれも
    404 ERR_CAPSULE_NOT_FOUND（存在秘匿）で返す。
    """
    stmt = (
        select(Capsule)
        .join(CapsuleMember, CapsuleMember.capsule_id == Capsule.id)
        .where(
            Capsule.id == capsule_id,
            CapsuleMember.user_id == current_user.id,
            CapsuleMember.status == "active",
        )
    )
    result = await session.execute(stmt)
    capsule = result.scalar_one_or_none()
    if capsule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_CAPSULE_NOT_FOUND", "message": "カプセルが見つかりません"},
        )
    return await _build_capsule_read(session, capsule, current_user.id)


@router.patch(
    "/{capsule_id}/open-date",
    response_model=CapsuleRead,
    summary="開封日変更",
)
async def update_open_date(
    capsule_id: UUID,
    body: CapsuleOpenDateUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CapsuleRead:
    """開封日を変更する。参加者全員が変更可能（api-spec §3.4）。

    認可判定は api-spec §3.4 のエラー表（401/403 ERR_NOT_CAPSULE_MEMBER/404/409/422）に
    従い、まずカプセルの存在（404）を確認し、次に active 参加者であること（403）を確認する。
    開封済み（unsealed_at 非 NULL）は 409 ERR_CAPSULE_ALREADY_UNSEALED。
    """
    capsule = await _get_capsule_or_404(session, capsule_id)
    await _require_active_membership(session, capsule_id, current_user.id)

    if capsule.unsealed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ERR_CAPSULE_ALREADY_UNSEALED", "message": "開封済みのカプセルは開封日を変更できません"},
        )
    if _is_in_past(body.open_at):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "ERR_OPEN_AT_IN_PAST", "message": "open_at は未来日時を指定してください"},
        )

    stmt = update(Capsule).where(Capsule.id == capsule_id).values(open_at=body.open_at, updated_at=func.now())
    await session.execute(stmt)
    # TODO(B3): open_at_change 通知を email_deliveries へキュー登録する（メール基盤未実装のため保留）
    await session.commit()
    await session.refresh(capsule)

    return await _build_capsule_read(session, capsule, current_user.id)
