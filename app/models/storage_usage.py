"""storage_usage テーブルモデル

カプセル単位のストレージ使用量スナップショット。
record_attachments INSERT トリガーにより即時 UPSERT。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StorageUsage(Base):
    __tablename__ = "storage_usage"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    capsule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="CASCADE", name="storage_usage_capsule_id_fkey"),
        nullable=False,
    )
    used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_calculated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        UniqueConstraint("capsule_id", name="storage_usage_capsule_id_unique"),
        CheckConstraint("used_bytes >= 0", name="storage_usage_used_bytes_check"),
        CheckConstraint("attachment_count >= 0", name="storage_usage_attachment_count_check"),
    )
