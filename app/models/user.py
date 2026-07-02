"""users テーブルモデル

Firebase Auth 認証済みユーザーのプロファイル・課金・状態管理。
物理削除禁止（論理削除のみ）。退会後5年で PII 匿名化。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    firebase_uid: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'ja'"))
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'Asia/Tokyo'"))
    current_plan: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'free'"))
    trial_ends_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    # IAP には Stripe の customer に相当する顧客ID概念がないため、課金識別子カラムは持たない。
    # ユーザー↔購読の紐付けは users.id（UUID）を appAccountToken / obfuscatedExternalAccountId
    # に流用して行う（詳細は data-model §3.1 / §4.7）。
    terms_agreed_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    terms_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("FALSE"))
    deleted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    anonymize_scheduled_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "current_plan IN ('free', 'paid_monthly', 'paid_yearly')",
            name="chk_users_current_plan",
        ),
        CheckConstraint(
            "is_deleted = FALSE OR deleted_at IS NOT NULL",
            name="users_deleted_at_required",
        ),
        CheckConstraint(
            "(terms_agreed_at IS NULL AND terms_version IS NULL) OR (terms_agreed_at IS NOT NULL AND terms_version IS NOT NULL)",
            name="users_terms_both_or_none",
        ),
    )
