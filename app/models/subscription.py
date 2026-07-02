"""subscriptions テーブルモデル

ユーザーのプラン契約状態の真実の源（source of truth）。
ただしその真実は Apple App Store / Google Play ストア側にあり、
当方 DB は Server-to-Server 通知（Apple App Store Server Notifications V2 /
Google Real-time Developer Notifications）と検証 API から取得した購読状態の
ミラーである。1 ユーザー 1 レコード（UNIQUE(user_id)）。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT", name="subscriptions_user_id_fkey"),
        nullable=False,
    )
    plan_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # === IAP 購読識別子（プラットフォーム別カラム方式）===
    # Apple originalTransactionId は不変、Google purchaseToken はローテーションするため
    # 単一カラムに混在させず別カラムに分離する（data-model §3.7）。
    platform: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_transaction_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_notification_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    latest_notification_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    auto_renew: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    current_period_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trial_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancel_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        UniqueConstraint("user_id", name="subscriptions_user_id_unique"),
        CheckConstraint(
            "plan_type IN ('free', 'paid_monthly', 'paid_yearly')",
            name="subscriptions_plan_type_check",
        ),
        CheckConstraint(
            "status IN ('trialing', 'active', 'in_grace_period', 'canceled', 'on_hold', 'expired')",
            name="subscriptions_status_check",
        ),
        CheckConstraint(
            "platform IS NULL OR platform IN ('apple', 'google')",
            name="subscriptions_platform_check",
        ),
        CheckConstraint(
            "environment IS NULL OR environment IN ('sandbox', 'production')",
            name="subscriptions_environment_check",
        ),
        CheckConstraint(
            "(plan_type = 'free' AND platform IS NULL "
            "AND original_transaction_id IS NULL AND purchase_token IS NULL) "
            "OR (platform = 'apple' AND original_transaction_id IS NOT NULL AND purchase_token IS NULL) "
            "OR (platform = 'google' AND purchase_token IS NOT NULL AND original_transaction_id IS NULL)",
            name="subscriptions_provider_identifier_consistency",
        ),
    )
