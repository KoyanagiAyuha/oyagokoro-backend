"""unseal_events テーブルモデル

タイムカプセル開封イベントの記録（1 開封 = 1 レコード）。
INSERT only。監査ログとして機能。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UnsealEvent(Base):
    __tablename__ = "unseal_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    capsule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="CASCADE", name="fk_unseal_events_capsule"),
        nullable=False,
    )
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 手動開封時は users.id を記録。自動開封時は NULL。
    executed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL", name="fk_unseal_events_executed_by"),
        nullable=True,
    )
    executed_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    notification_sent_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('manual', 'scheduled')",
            name="chk_unseal_events_trigger_type",
        ),
    )
