"""capsules テーブルモデル

タイムカプセル（グループ）本体。開封日・封印状態・創設者を管理。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Capsule(Base):
    __tablename__ = "capsules"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    open_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    unsealed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    unseal_trigger: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="capsules_created_by_fkey"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "unseal_trigger IN ('manual', 'scheduled')",
            name="capsules_unseal_trigger_check",
        ),
        CheckConstraint(
            "(unsealed_at IS NULL AND unseal_trigger IS NULL) OR (unsealed_at IS NOT NULL AND unseal_trigger IS NOT NULL)",
            name="capsules_unseal_consistency",
        ),
    )
