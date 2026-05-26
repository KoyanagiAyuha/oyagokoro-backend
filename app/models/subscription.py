"""subscriptions テーブルモデル

ユーザーのプラン契約状態の真実の源（source of truth）。
Stripe サブスクリプションと 1:1 対応。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID as PG_UUID
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
    stripe_subscription_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    current_period_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trial_start: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    cancel_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()")
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="subscriptions_user_id_unique"),
        CheckConstraint(
            "plan_type IN ('free', 'paid_monthly', 'paid_yearly')",
            name="subscriptions_plan_type_check",
        ),
        CheckConstraint(
            "status IN ('trialing', 'active', 'past_due', 'canceled', 'unpaid')",
            name="subscriptions_status_check",
        ),
    )
