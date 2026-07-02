"""delivery_addresses テーブルモデル

開封時の配信先メールアドレスリスト。
バウンス状態・タグフィルタ・追加者追跡を管理。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DeliveryAddress(Base):
    __tablename__ = "delivery_addresses"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    capsule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="CASCADE", name="fk_delivery_addresses_capsule"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    tag: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'all'"))
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("TRUE"))
    added_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_delivery_addresses_added_by"),
        nullable=True,
    )
    last_bounced_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    bounce_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    paused_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "tag IN ('all', 'parents_only')",
            name="chk_delivery_addresses_tag",
        ),
    )
