"""storage_purchases テーブルモデル

追加ストレージの買い切り購入履歴（10GB / 1,500 円）。
取り消し不可・不変テーブル。
expires_at は purchased_at から GENERATED ALWAYS AS で自動計算。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class StoragePurchase(Base):
    __tablename__ = "storage_purchases"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="storage_purchases_user_id_fkey"),
        nullable=False,
    )
    stripe_payment_intent_id: Mapped[str] = mapped_column(Text, nullable=False)
    gb_added: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    price_jpy: Mapped[int] = mapped_column(Integer, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    # 購入日から 20 年後に自動計算（GENERATED ALWAYS AS STORED）
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        Computed("purchased_at + INTERVAL '20 years'", persisted=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        UniqueConstraint("stripe_payment_intent_id", name="storage_purchases_stripe_payment_intent_id_unique"),
        CheckConstraint("gb_added > 0", name="storage_purchases_gb_added_check"),
        CheckConstraint("price_jpy >= 0", name="storage_purchases_price_jpy_check"),
    )
