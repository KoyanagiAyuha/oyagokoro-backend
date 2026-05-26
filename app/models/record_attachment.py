"""record_attachments テーブルモデル

記録に紐付く画像・音声ファイルの S3 参照メタデータ。
INSERT only（変更・削除禁止）。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecordAttachment(Base):
    __tablename__ = "record_attachments"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    record_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("records.id", ondelete="RESTRICT", name="fk_record_attachments_record"),
        nullable=False,
    )
    attachment_type: Mapped[str] = mapped_column(Text, nullable=False)
    s3_object_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        CheckConstraint(
            "attachment_type IN ('image', 'audio')",
            name="chk_record_attachments_type",
        ),
        CheckConstraint(
            "byte_size > 0",
            name="chk_record_attachments_byte_size",
        ),
        CheckConstraint(
            "char_length(s3_object_key) > 0",
            name="chk_record_attachments_s3_key_nonempty",
        ),
        CheckConstraint(
            "(attachment_type = 'audio' AND duration_seconds IS NOT NULL) OR (attachment_type = 'image' AND duration_seconds IS NULL)",
            name="chk_record_attachments_duration",
        ),
        CheckConstraint(
            "(attachment_type = 'image' AND width IS NOT NULL AND height IS NOT NULL) OR (attachment_type = 'audio' AND width IS NULL AND height IS NULL)",
            name="chk_record_attachments_dimensions",
        ),
    )
