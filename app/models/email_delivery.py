"""email_deliveries テーブルモデル

メール配信ログ（開封通知・記録配信・招待・バウンス警告・開封日変更）。
リトライ管理（最大 3 回・24 時間以内）。
unseal_event_id は NULL 許容（R-08 対応）。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EmailDelivery(Base):
    __tablename__ = "email_deliveries"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    capsule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="CASCADE", name="fk_email_deliveries_capsule"),
        nullable=False,
    )
    # 記録配信時に設定。開封通知は NULL。
    record_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("records.id", ondelete="RESTRICT", name="fk_email_deliveries_record"),
        nullable=True,
    )
    delivery_address_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("delivery_addresses.id", ondelete="RESTRICT", name="fk_email_deliveries_delivery_address"),
        nullable=False,
    )
    # R-08 対応: unseal_notice/record_delivery は必須、invite/bounce_warning/open_at_change は NULL
    unseal_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("unseal_events.id", ondelete="RESTRICT", name="fk_email_deliveries_unseal_event"),
        nullable=True,
    )
    email_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resend_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("1"))
    last_attempted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    skipped_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "email_type IN ('unseal_notice', 'record_delivery', 'invite', 'bounce_warning', 'open_at_change')",
            name="chk_email_deliveries_email_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'sent', 'delivered', 'bounced', 'failed', 'skipped')",
            name="chk_email_deliveries_status",
        ),
        CheckConstraint(
            "attempt_count BETWEEN 1 AND 3",
            name="chk_email_deliveries_attempt_count",
        ),
        # R-08 対応: email_type と unseal_event_id の整合性
        CheckConstraint(
            "(email_type IN ('unseal_notice', 'record_delivery') AND unseal_event_id IS NOT NULL) OR (email_type IN ('invite', 'bounce_warning', 'open_at_change') AND unseal_event_id IS NULL)",
            name="chk_email_deliveries_unseal_event_consistency",
        ),
    )
