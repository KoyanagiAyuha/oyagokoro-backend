"""Capsule 関連の Pydantic スキーマ"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CapsuleMembershipRead(BaseModel):
    """CapsuleRead.my_membership の表現"""

    model_config = ConfigDict(from_attributes=True)

    member_id: UUID
    status: str


class CapsuleRead(BaseModel):
    """GET/POST /api/v1/capsules 系レスポンスで返す Capsule 表現（api-spec §3 冒頭）"""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    open_at: datetime
    unsealed_at: datetime | None
    unseal_trigger: str | None
    is_frozen: bool
    created_by: UUID
    member_count: int
    my_membership: CapsuleMembershipRead | None
    created_at: datetime
    updated_at: datetime


class CapsuleCreateRequest(BaseModel):
    """POST /api/v1/capsules のリクエストボディ"""

    name: str = Field(min_length=1, max_length=255)
    open_at: datetime


class CapsuleOpenDateUpdateRequest(BaseModel):
    """PATCH /api/v1/capsules/{capsuleId}/open-date のリクエストボディ"""

    open_at: datetime


class CapsuleListResponse(BaseModel):
    """GET /api/v1/capsules のレスポンス"""

    items: list[CapsuleRead]
    total: int
