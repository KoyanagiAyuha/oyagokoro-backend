"""capsule_members テーブルモデル

タイムカプセルへの参加関係。invited / active / deleted の3状態で管理。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CapsuleMember(Base):
    __tablename__ = "capsule_members"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    capsule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="RESTRICT", name="capsule_members_capsule_id_fkey"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="capsule_members_user_id_fkey"),
        nullable=True,
    )
    invited_email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'invited'"))
    invited_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    joined_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    deletion_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_name_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('invited', 'active', 'deleted')",
            name="capsule_members_status_check",
        ),
        CheckConstraint(
            "deletion_reason IN ('self_exit', 'removed_by_member')",
            name="capsule_members_deletion_reason_check",
        ),
        CheckConstraint(
            "(status = 'deleted' AND deleted_at IS NOT NULL AND deletion_reason IS NOT NULL) OR (status != 'deleted' AND deleted_at IS NULL AND deletion_reason IS NULL)",
            name="capsule_members_deleted_consistency",
        ),
        CheckConstraint(
            "(status = 'active' AND joined_at IS NOT NULL) OR (status != 'active')",
            name="capsule_members_active_consistency",
        ),
    )
