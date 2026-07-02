"""storage_purchases テーブルモデル

追加ストレージの買い切り（消費型 IAP）購入履歴（10GB / 1,500 円）。
原則不変（INSERT only）だが、消費型 IAP は返金（Apple REFUND /
Google VOIDED_PURCHASE）が現実に起こり得るため、返金時のみ revoked_at の
更新を許可する（RLS の詳細は init migration / data-model §3.8）。
冪等キーは UNIQUE(platform, provider_transaction_id)。
expires_at は BEFORE INSERT トリガー（set_storage_purchases_expires_at）で自動設定
（v0.4: PostgreSQL の immutable 制約により GENERATED ALWAYS AS から変更）。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
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
    # === IAP 消費型購入の識別子 ===
    # provider_transaction_id は冪等キー。Apple = transactionId / Google = purchaseToken。
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    provider_transaction_id: Mapped[str] = mapped_column(Text, nullable=False)
    # provider_order_id は Google orderId（GPA.xxxx）等。サポート・突合用。Apple は NULL。
    provider_order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    gb_added: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("10"))
    price_jpy: Mapped[int] = mapped_column(Integer, nullable=False)
    purchased_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    # expires_at は BEFORE INSERT トリガー（set_storage_purchases_expires_at）で
    # purchased_at + INTERVAL '20 years' に自動設定される。
    # PostgreSQL の immutable 制約により GENERATED ALWAYS AS は使えないため
    # トリガー方式に変更（v0.4 対応）。
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=text("NOW()"),  # 暫定値、トリガーで即時上書き
    )
    # revoked_at: 返金・チャージバックで無効化された時刻。NULL = 有効。
    revoked_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        UniqueConstraint(
            "platform",
            "provider_transaction_id",
            name="storage_purchases_platform_provider_txn_unique",
        ),
        CheckConstraint("gb_added > 0", name="storage_purchases_gb_added_check"),
        CheckConstraint("price_jpy >= 0", name="storage_purchases_price_jpy_check"),
        CheckConstraint(
            "platform IN ('apple', 'google')",
            name="storage_purchases_platform_check",
        ),
        CheckConstraint(
            "environment IS NULL OR environment IN ('sandbox', 'production')",
            name="storage_purchases_environment_check",
        ),
    )
