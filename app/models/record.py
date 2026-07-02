"""records テーブルモデル

タイムカプセルへの投稿本文。INSERT only（変更・削除禁止）。
window_ends_at は GENERATED ALWAYS AS で自動計算（Computed persisted）。
計算式: 投稿日翌日 0:00 JST 起算で 7 日間。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Record(Base):
    __tablename__ = "records"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    capsule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("capsules.id", ondelete="RESTRICT", name="fk_records_capsule"),
        nullable=False,
    )
    author_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="fk_records_author"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'all'"))
    posted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    # GENERATED ALWAYS AS (投稿日翌日 0:00 JST 起算で 7 日間) STORED
    # v0.4: Computed 式を timezone() 関数形式に変更（AT TIME ZONE 演算子形式から）
    window_ends_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        Computed(
            "timezone('Asia/Tokyo', date_trunc('day', timezone('Asia/Tokyo', posted_at)) + INTERVAL '8 days')",
            persisted=True,
        ),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "char_length(body) BETWEEN 1 AND 5000",
            name="chk_records_body_length",
        ),
        CheckConstraint(
            "visibility IN ('all', 'parents_only')",
            name="chk_records_visibility",
        ),
        CheckConstraint(
            "window_ends_at > posted_at",
            name="chk_records_window_after_posted",
        ),
    )
