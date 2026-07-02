"""init

Revision ID: c56b822a5394
Revises:
Create Date: 2026-05-27 03:47:54.978657

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c56b822a5394"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""

    # === 0. 拡張機能・ロール（autogenerate 非対応）===
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_role') THEN
                CREATE ROLE app_role NOLOGIN;
            END IF;
        END
        $$;
    """)

    # === 1. テーブル作成（autogenerate）===
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("firebase_uid", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("locale", sa.Text(), server_default=sa.text("'ja'"), nullable=False),
        sa.Column("timezone", sa.Text(), server_default=sa.text("'Asia/Tokyo'"), nullable=False),
        sa.Column("current_plan", sa.Text(), server_default=sa.text("'free'"), nullable=False),
        sa.Column("trial_ends_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("terms_agreed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("terms_version", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("FALSE"), nullable=False),
        sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("anonymize_scheduled_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("current_plan IN ('free', 'paid_monthly', 'paid_yearly')", name="chk_users_current_plan"),
        sa.CheckConstraint(
            "(terms_agreed_at IS NULL AND terms_version IS NULL) OR (terms_agreed_at IS NOT NULL AND terms_version IS NOT NULL)",
            name="users_terms_both_or_none",
        ),
        sa.CheckConstraint("is_deleted = FALSE OR deleted_at IS NOT NULL", name="users_deleted_at_required"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("firebase_uid"),
    )
    op.create_table(
        "capsules",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("open_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("unsealed_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("unseal_trigger", sa.String(length=20), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("unseal_trigger IN ('manual', 'scheduled')", name="capsules_unseal_trigger_check"),
        sa.CheckConstraint(
            "(unsealed_at IS NULL AND unseal_trigger IS NULL) OR (unsealed_at IS NOT NULL AND unseal_trigger IS NOT NULL)",
            name="capsules_unseal_consistency",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="capsules_created_by_fkey", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("""
        CREATE TABLE storage_purchases (
            id                        UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id                   UUID        NOT NULL,
            -- IAP 消費型購入の識別子。provider_transaction_id が冪等キー
            -- （Apple = transactionId / Google = purchaseToken）
            platform                  TEXT        NOT NULL,
            provider_transaction_id   TEXT        NOT NULL,
            provider_order_id         TEXT,
            product_id                TEXT        NOT NULL,
            environment               TEXT,
            gb_added                  INTEGER     NOT NULL DEFAULT 10,
            price_jpy                 INTEGER     NOT NULL,
            purchased_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            -- expires_at は BEFORE INSERT トリガー（set_storage_purchases_expires_at）で自動セット
            -- schema.sql では GENERATED ALWAYS AS だが TIMESTAMPTZ + INTERVAL が PostgreSQL immutable 制約に引っかかるため
            -- トリガー方式で同等の不変性を担保する
            expires_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            -- revoked_at: 返金・チャージバックで無効化された時刻。NULL = 有効
            revoked_at                TIMESTAMPTZ,
            created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT storage_purchases_user_id_fkey
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT,
            CONSTRAINT storage_purchases_platform_provider_txn_unique
                UNIQUE (platform, provider_transaction_id),
            CONSTRAINT storage_purchases_gb_added_check
                CHECK (gb_added > 0),
            CONSTRAINT storage_purchases_price_jpy_check
                CHECK (price_jpy >= 0),
            CONSTRAINT storage_purchases_platform_check
                CHECK (platform IN ('apple', 'google')),
            CONSTRAINT storage_purchases_environment_check
                CHECK (environment IS NULL OR environment IN ('sandbox', 'production'))
        )
    """)
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("plan_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        # IAP 購読識別子（プラットフォーム別カラム方式。data-model §3.7）
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("original_transaction_id", sa.Text(), nullable=True),
        sa.Column("purchase_token", sa.Text(), nullable=True),
        sa.Column("product_id", sa.Text(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=True),
        sa.Column("latest_notification_type", sa.Text(), nullable=True),
        sa.Column("latest_notification_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("auto_renew", sa.Boolean(), nullable=True),
        sa.Column("current_period_start", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("current_period_end", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("trial_start", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("trial_end", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("cancel_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("canceled_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "plan_type IN ('free', 'paid_monthly', 'paid_yearly')", name="subscriptions_plan_type_check"
        ),
        sa.CheckConstraint(
            "status IN ('trialing', 'active', 'in_grace_period', 'canceled', 'on_hold', 'expired')",
            name="subscriptions_status_check",
        ),
        sa.CheckConstraint("platform IS NULL OR platform IN ('apple', 'google')", name="subscriptions_platform_check"),
        sa.CheckConstraint(
            "environment IS NULL OR environment IN ('sandbox', 'production')", name="subscriptions_environment_check"
        ),
        sa.CheckConstraint(
            "(plan_type = 'free' AND platform IS NULL AND original_transaction_id IS NULL AND purchase_token IS NULL) OR (platform = 'apple' AND original_transaction_id IS NOT NULL AND purchase_token IS NULL) OR (platform = 'google' AND purchase_token IS NOT NULL AND original_transaction_id IS NULL)",
            name="subscriptions_provider_identifier_consistency",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="subscriptions_user_id_fkey", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="subscriptions_user_id_unique"),
    )
    op.create_table(
        "capsule_members",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("capsule_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("invited_email", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'invited'"), nullable=False),
        sa.Column("invited_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("joined_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deleted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("deletion_reason", sa.String(length=50), nullable=True),
        sa.Column("display_name_override", sa.String(length=255), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "(status = 'active' AND joined_at IS NOT NULL) OR (status != 'active')",
            name="capsule_members_active_consistency",
        ),
        sa.CheckConstraint(
            "(status = 'deleted' AND deleted_at IS NOT NULL AND deletion_reason IS NOT NULL) OR (status != 'deleted' AND deleted_at IS NULL AND deletion_reason IS NULL)",
            name="capsule_members_deleted_consistency",
        ),
        sa.CheckConstraint(
            "deletion_reason IN ('self_exit', 'removed_by_member')", name="capsule_members_deletion_reason_check"
        ),
        sa.CheckConstraint("status IN ('invited', 'active', 'deleted')", name="capsule_members_status_check"),
        sa.ForeignKeyConstraint(
            ["capsule_id"], ["capsules.id"], name="capsule_members_capsule_id_fkey", ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="capsule_members_user_id_fkey", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "delivery_addresses",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("capsule_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("tag", sa.String(length=20), server_default=sa.text("'all'"), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("TRUE"), nullable=False),
        sa.Column("added_by", sa.UUID(), nullable=True),
        sa.Column("last_bounced_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("bounce_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("paused_reason", sa.String(length=200), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("tag IN ('all', 'parents_only')", name="chk_delivery_addresses_tag"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], name="fk_delivery_addresses_added_by", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["capsule_id"], ["capsules.id"], name="fk_delivery_addresses_capsule", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("""
        CREATE TABLE records (
            id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            capsule_id      UUID        NOT NULL,
            author_id       UUID        NOT NULL,
            body            TEXT        NOT NULL,
            visibility      TEXT        NOT NULL DEFAULT 'all',
            posted_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            -- window_ends_at は timezone() 関数形式で GENERATED ALWAYS AS を実現
            -- AT TIME ZONE 演算子は volatile だが timezone(text, timestamptz) 関数は immutable
            window_ends_at  TIMESTAMPTZ GENERATED ALWAYS AS (
                                timezone('Asia/Tokyo',
                                    date_trunc('day', timezone('Asia/Tokyo', posted_at)) + INTERVAL '8 days'
                                )
                            ) STORED,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_records_body_length
                CHECK (char_length(body) BETWEEN 1 AND 5000),
            CONSTRAINT chk_records_visibility
                CHECK (visibility IN ('all', 'parents_only')),
            CONSTRAINT chk_records_window_after_posted
                CHECK (window_ends_at > posted_at),
            CONSTRAINT fk_records_author
                FOREIGN KEY (author_id) REFERENCES users (id) ON DELETE RESTRICT,
            CONSTRAINT fk_records_capsule
                FOREIGN KEY (capsule_id) REFERENCES capsules (id) ON DELETE RESTRICT
        )
    """)
    op.create_table(
        "storage_usage",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("capsule_id", sa.UUID(), nullable=False),
        sa.Column("used_bytes", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("attachment_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "last_calculated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False
        ),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("attachment_count >= 0", name="storage_usage_attachment_count_check"),
        sa.CheckConstraint("used_bytes >= 0", name="storage_usage_used_bytes_check"),
        sa.ForeignKeyConstraint(
            ["capsule_id"], ["capsules.id"], name="storage_usage_capsule_id_fkey", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("capsule_id", name="storage_usage_capsule_id_unique"),
    )
    op.create_table(
        "unseal_events",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("capsule_id", sa.UUID(), nullable=False),
        sa.Column("trigger_type", sa.String(length=20), nullable=False),
        sa.Column("executed_by", sa.UUID(), nullable=True),
        sa.Column("executed_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("notification_sent_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint("trigger_type IN ('manual', 'scheduled')", name="chk_unseal_events_trigger_type"),
        sa.ForeignKeyConstraint(["capsule_id"], ["capsules.id"], name="fk_unseal_events_capsule", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["executed_by"], ["users.id"], name="fk_unseal_events_executed_by", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("capsule_id", sa.UUID(), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=True),
        sa.Column("delivery_address_id", sa.UUID(), nullable=False),
        sa.Column("unseal_event_id", sa.UUID(), nullable=True),
        sa.Column("email_type", sa.String(length=50), nullable=False),
        sa.Column("resend_message_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("attempt_count", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_attempted_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("skipped_reason", sa.String(length=100), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "(email_type IN ('unseal_notice', 'record_delivery') AND unseal_event_id IS NOT NULL) OR (email_type IN ('invite', 'bounce_warning', 'open_at_change') AND unseal_event_id IS NULL)",
            name="chk_email_deliveries_unseal_event_consistency",
        ),
        sa.CheckConstraint(
            "email_type IN ('unseal_notice', 'record_delivery', 'invite', 'bounce_warning', 'open_at_change')",
            name="chk_email_deliveries_email_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'delivered', 'bounced', 'failed', 'skipped')",
            name="chk_email_deliveries_status",
        ),
        sa.CheckConstraint("attempt_count BETWEEN 1 AND 3", name="chk_email_deliveries_attempt_count"),
        sa.ForeignKeyConstraint(
            ["capsule_id"], ["capsules.id"], name="fk_email_deliveries_capsule", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["delivery_address_id"],
            ["delivery_addresses.id"],
            name="fk_email_deliveries_delivery_address",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["record_id"], ["records.id"], name="fk_email_deliveries_record", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["unseal_event_id"], ["unseal_events.id"], name="fk_email_deliveries_unseal_event", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "record_attachments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("attachment_type", sa.Text(), nullable=False),
        sa.Column("s3_object_key", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.CheckConstraint(
            "(attachment_type = 'audio' AND duration_seconds IS NOT NULL) OR (attachment_type = 'image' AND duration_seconds IS NULL)",
            name="chk_record_attachments_duration",
        ),
        sa.CheckConstraint(
            "(attachment_type = 'image' AND width IS NOT NULL AND height IS NOT NULL) OR (attachment_type = 'audio' AND width IS NULL AND height IS NULL)",
            name="chk_record_attachments_dimensions",
        ),
        sa.CheckConstraint("attachment_type IN ('image', 'audio')", name="chk_record_attachments_type"),
        sa.CheckConstraint("byte_size > 0", name="chk_record_attachments_byte_size"),
        sa.CheckConstraint("char_length(s3_object_key) > 0", name="chk_record_attachments_s3_key_nonempty"),
        sa.ForeignKeyConstraint(
            ["record_id"], ["records.id"], name="fk_record_attachments_record", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # === 2. 共通関数 ===

    # updated_at 自動更新トリガー関数
    op.execute("""
        CREATE OR REPLACE FUNCTION trigger_set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # records / record_attachments / unseal_events / storage_purchases 変更防御トリガー関数
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_records_mutation()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION '記録の変更・削除は禁止されています（INSERT only）。仕様 §9.7 参照。';
        END;
        $$;
    """)

    # storage_usage 即時更新トリガー関数
    op.execute("""
        CREATE OR REPLACE FUNCTION update_storage_usage()
        RETURNS TRIGGER AS $$
        DECLARE
            v_capsule_id UUID;
        BEGIN
            IF NEW.byte_size IS NULL OR NEW.byte_size <= 0 THEN
                RETURN NEW;
            END IF;

            SELECT capsule_id INTO v_capsule_id
                FROM records WHERE id = NEW.record_id;

            INSERT INTO storage_usage (capsule_id, used_bytes, attachment_count, last_calculated_at, updated_at)
            VALUES (v_capsule_id, NEW.byte_size, 1, NOW(), NOW())
            ON CONFLICT (capsule_id) DO UPDATE
                SET used_bytes          = storage_usage.used_bytes + EXCLUDED.used_bytes,
                    attachment_count    = storage_usage.attachment_count + EXCLUDED.attachment_count,
                    last_calculated_at  = NOW();

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # delivery_addresses / capsule_members の email 正規化トリガー関数
    op.execute("""
        CREATE OR REPLACE FUNCTION normalize_email_lower()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_TABLE_NAME = 'delivery_addresses' THEN
                NEW.email := LOWER(NEW.email);
            ELSIF TG_TABLE_NAME = 'capsule_members' THEN
                NEW.invited_email := LOWER(NEW.invited_email);
            END IF;
            RETURN NEW;
        END;
        $$;
    """)

    # storage_purchases.expires_at 自動セットトリガー関数
    # schema.sql では GENERATED ALWAYS AS だが TIMESTAMPTZ + INTERVAL が
    # PostgreSQL immutable 制約に引っかかるため BEFORE INSERT トリガーで代替
    op.execute("""
        CREATE OR REPLACE FUNCTION set_storage_purchases_expires_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.expires_at := NEW.purchased_at + INTERVAL '20 years';
            RETURN NEW;
        END;
        $$;
    """)

    # === 3. インデックス ===

    # --- users ---
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_firebase_uid ON users (firebase_uid)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_is_deleted ON users (is_deleted) WHERE is_deleted = FALSE")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_trial_ends_at ON users (trial_ends_at) WHERE trial_ends_at IS NOT NULL AND is_deleted = FALSE"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_anonymize_scheduled_at ON users (anonymize_scheduled_at) WHERE anonymize_scheduled_at IS NOT NULL"
    )

    # --- capsules ---
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_capsules_open_at_unsealed ON capsules (open_at) WHERE unsealed_at IS NULL"
    )

    # --- capsule_members ---
    op.execute("CREATE INDEX IF NOT EXISTS idx_capsule_members_capsule_id ON capsule_members (capsule_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_capsule_members_user_id ON capsule_members (user_id) WHERE user_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_capsule_members_capsule_email ON capsule_members (capsule_id, LOWER(invited_email))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_capsule_members_active ON capsule_members (capsule_id, status) WHERE status = 'active'"
    )

    # --- records ---
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_records_capsule_window ON records (capsule_id, window_ends_at) WHERE window_ends_at IS NOT NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_records_author_posted ON records (author_id, posted_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_records_capsule_posted ON records (capsule_id, posted_at DESC)")

    # --- record_attachments ---
    op.execute("CREATE INDEX IF NOT EXISTS idx_record_attachments_record_id ON record_attachments (record_id)")

    # --- delivery_addresses ---
    op.execute("CREATE INDEX IF NOT EXISTS idx_delivery_addresses_capsule_id ON delivery_addresses (capsule_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_addresses_is_active ON delivery_addresses (capsule_id, is_active) WHERE is_active = TRUE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_delivery_addresses_tag ON delivery_addresses (capsule_id, tag)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_delivery_addresses_added_by ON delivery_addresses (added_by) WHERE added_by IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_delivery_addresses_email_capsule ON delivery_addresses (capsule_id, LOWER(email))"
    )

    # --- subscriptions ---
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions (user_id)")
    # プラットフォーム別 部分UNIQUE（識別子の重複購読防止・冪等UPSERTのキー）
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_apple_otxn ON subscriptions (original_transaction_id) WHERE original_transaction_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_subscriptions_google_token ON subscriptions (purchase_token) WHERE purchase_token IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_status_active ON subscriptions (status) WHERE status IN ('trialing', 'active', 'in_grace_period', 'canceled')"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_subscriptions_trial_end ON subscriptions (trial_end) WHERE trial_end IS NOT NULL"
    )

    # --- storage_purchases ---
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_storage_purchases_provider_txn ON storage_purchases (platform, provider_transaction_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_storage_purchases_user_id ON storage_purchases (user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_storage_purchases_expires_at ON storage_purchases (expires_at)")
    # 有効付与量の集計を速める（返金・期限切れを除外）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_storage_purchases_effective ON storage_purchases (user_id) WHERE revoked_at IS NULL"
    )

    # --- storage_usage ---
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_storage_usage_capsule_id ON storage_usage (capsule_id)")

    # --- unseal_events ---
    op.execute("CREATE INDEX IF NOT EXISTS idx_unseal_events_capsule_id ON unseal_events (capsule_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_unseal_events_notification_pending ON unseal_events (capsule_id, notification_sent_at) WHERE notification_sent_at IS NULL"
    )

    # --- email_deliveries ---
    op.execute("CREATE INDEX IF NOT EXISTS idx_email_deliveries_capsule_id ON email_deliveries (capsule_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_deliveries_unseal_event_delivery ON email_deliveries (unseal_event_id, delivery_address_id) WHERE unseal_event_id IS NOT NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_deliveries_retry_candidates ON email_deliveries (status, attempt_count, last_attempted_at) WHERE status = 'failed' AND attempt_count < 3"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_deliveries_delivery_address ON email_deliveries (delivery_address_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_email_deliveries_record_id ON email_deliveries (record_id) WHERE record_id IS NOT NULL"
    )

    # === 4. トリガー ===

    # --- updated_at 自動更新トリガー ---
    op.execute("""
        CREATE TRIGGER trg_users_updated_at
            BEFORE UPDATE ON users
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_capsules_updated_at
            BEFORE UPDATE ON capsules
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_delivery_addresses_updated_at
            BEFORE UPDATE ON delivery_addresses
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_subscriptions_updated_at
            BEFORE UPDATE ON subscriptions
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_storage_usage_updated_at
            BEFORE UPDATE ON storage_usage
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_email_deliveries_updated_at
            BEFORE UPDATE ON email_deliveries
            FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at()
    """)

    # --- records: INSERT only 強制トリガー ---
    op.execute("""
        CREATE TRIGGER trg_records_no_update
            BEFORE UPDATE ON records
            FOR EACH ROW EXECUTE FUNCTION prevent_records_mutation()
    """)
    op.execute("""
        CREATE TRIGGER trg_records_no_delete
            BEFORE DELETE ON records
            FOR EACH ROW EXECUTE FUNCTION prevent_records_mutation()
    """)
    op.execute("""
        CREATE TRIGGER trg_records_no_truncate
            BEFORE TRUNCATE ON records
            FOR EACH STATEMENT EXECUTE FUNCTION prevent_records_mutation()
    """)

    # --- record_attachments: INSERT only 強制トリガー ---
    op.execute("""
        CREATE TRIGGER trg_record_attachments_no_update
            BEFORE UPDATE ON record_attachments
            FOR EACH ROW EXECUTE FUNCTION prevent_records_mutation()
    """)
    op.execute("""
        CREATE TRIGGER trg_record_attachments_no_delete
            BEFORE DELETE ON record_attachments
            FOR EACH ROW EXECUTE FUNCTION prevent_records_mutation()
    """)
    op.execute("""
        CREATE TRIGGER trg_record_attachments_no_truncate
            BEFORE TRUNCATE ON record_attachments
            FOR EACH STATEMENT EXECUTE FUNCTION prevent_records_mutation()
    """)

    # --- unseal_events: TRUNCATE 防御トリガー ---
    op.execute("""
        CREATE TRIGGER trg_unseal_events_no_truncate
            BEFORE TRUNCATE ON unseal_events
            FOR EACH STATEMENT EXECUTE FUNCTION prevent_records_mutation()
    """)

    # --- storage_purchases: TRUNCATE 防御トリガー ---
    op.execute("""
        CREATE TRIGGER trg_storage_purchases_no_truncate
            BEFORE TRUNCATE ON storage_purchases
            FOR EACH STATEMENT EXECUTE FUNCTION prevent_records_mutation()
    """)

    # --- delivery_addresses: email 正規化トリガー ---
    op.execute("""
        CREATE TRIGGER trg_delivery_addresses_normalize_email
            BEFORE INSERT OR UPDATE ON delivery_addresses
            FOR EACH ROW EXECUTE FUNCTION normalize_email_lower()
    """)

    # --- capsule_members: invited_email 正規化トリガー ---
    op.execute("""
        CREATE TRIGGER trg_capsule_members_normalize_email
            BEFORE INSERT OR UPDATE ON capsule_members
            FOR EACH ROW EXECUTE FUNCTION normalize_email_lower()
    """)

    # --- record_attachments → storage_usage 即時更新トリガー ---
    op.execute("""
        CREATE TRIGGER trg_update_storage_usage
            AFTER INSERT ON record_attachments
            FOR EACH ROW EXECUTE FUNCTION update_storage_usage()
    """)

    # --- storage_purchases: expires_at 自動セットトリガー ---
    # GENERATED ALWAYS AS の代替（TIMESTAMPTZ + INTERVAL が immutable 制約に引っかかるため）
    op.execute("""
        CREATE TRIGGER trg_storage_purchases_set_expires_at
            BEFORE INSERT ON storage_purchases
            FOR EACH ROW EXECUTE FUNCTION set_storage_purchases_expires_at()
    """)

    # === 5. RLS（Row Level Security）===

    op.execute("ALTER TABLE storage_purchases ENABLE ROW LEVEL SECURITY")

    op.execute("""
        CREATE POLICY storage_purchases_insert_only
            ON storage_purchases
            AS PERMISSIVE
            FOR INSERT
            TO app_role
            WITH CHECK (true)
    """)

    op.execute("""
        CREATE POLICY storage_purchases_select_own
            ON storage_purchases
            AS PERMISSIVE
            FOR SELECT
            TO app_role
            USING (true)
    """)

    # === 6. テーブル / カラムコメント ===

    op.execute(
        """COMMENT ON TABLE users IS 'Firebase Auth 認証済みユーザーのプロファイル・課金・状態管理。物理削除禁止（論理削除のみ）。退会後5年で PII 匿名化（A案採用）。'"""
    )
    op.execute(
        """COMMENT ON COLUMN users.anonymize_scheduled_at IS '退会5年後の PII 匿名化予約日時。匿名化対象: display_name / email / firebase_uid 等。Vercel Cron バッチで実施。records は永続保持する（B-5 A案）。'"""
    )
    op.execute(
        """COMMENT ON TABLE capsules IS 'タイムカプセル（グループ）本体。開封日・封印状態・創設者を管理する。'"""
    )
    op.execute(
        """COMMENT ON TABLE capsule_members IS 'タイムカプセルへの参加関係。invited / active / deleted の3状態で管理する。'"""
    )
    op.execute(
        """COMMENT ON TABLE records IS 'タイムカプセルへの投稿本文。INSERT only（変更・削除禁止）。window_ends_at は GENERATED ALWAYS AS で自動計算（トリガー不要）。'"""
    )
    op.execute(
        """COMMENT ON TABLE record_attachments IS '記録に紐付く画像・音声の S3 参照メタデータ。byte_size の合計がストレージ消費量の基準。INSERT only（変更・削除禁止）。'"""
    )
    op.execute(
        """COMMENT ON TABLE delivery_addresses IS '開封時の配信先メールアドレスリスト。バウンス状態・タグフィルタ・追加者追跡を管理。email は LOWER() で正規化済み。'"""
    )
    op.execute(
        """COMMENT ON TABLE subscriptions IS 'ユーザーのプラン契約状態の真実の源（source of truth）。真実は Apple/Google ストア側にあり、当方 DB は S2S 通知（Apple ASSN V2 / Google RTDN）＋検証 API から取得した状態のミラー。1 ユーザー 1 レコード。'"""
    )
    op.execute(
        """COMMENT ON TABLE storage_purchases IS '追加ストレージ買い切り（消費型 IAP）購入履歴（10GB / 1,500 円）。原則不変（INSERT only）だが返金時のみ revoked_at の UPDATE を許可。冪等キーは UNIQUE(platform, provider_transaction_id)。expires_at は BEFORE INSERT トリガー（set_storage_purchases_expires_at）で自動設定（v0.4: GENERATED ALWAYS AS から変更）。'"""
    )
    op.execute(
        """COMMENT ON TABLE storage_usage IS 'カプセル単位のストレージ使用量スナップショット。record_attachments INSERT トリガーにより即時更新。'"""
    )
    op.execute(
        """COMMENT ON TABLE unseal_events IS 'タイムカプセル開封イベントの記録（1 開封 = 1 レコード）。INSERT only。監査ログとして機能。executed_by は users(id) 参照（B-1 対応）。'"""
    )
    op.execute(
        """COMMENT ON COLUMN unseal_events.executed_by IS '手動開封時の実行者（users.id）。自動開封時は NULL。users は物理削除禁止のため20年後も追跡可能。'"""
    )
    op.execute(
        """COMMENT ON TABLE email_deliveries IS 'メール配信ログ（開封通知・記録配信・招待・バウンス警告・開封日変更）。リトライ管理（最大 3 回・24 時間以内）。'"""
    )


def downgrade() -> None:
    """Downgrade schema."""

    # === 1. RLS ポリシー DROP ===
    op.execute("DROP POLICY IF EXISTS storage_purchases_select_own ON storage_purchases")
    op.execute("DROP POLICY IF EXISTS storage_purchases_insert_only ON storage_purchases")
    op.execute("ALTER TABLE storage_purchases DISABLE ROW LEVEL SECURITY")

    # === 2. トリガー DROP ===
    op.execute("DROP TRIGGER IF EXISTS trg_storage_purchases_set_expires_at ON storage_purchases")
    op.execute("DROP TRIGGER IF EXISTS trg_update_storage_usage ON record_attachments")
    op.execute("DROP TRIGGER IF EXISTS trg_capsule_members_normalize_email ON capsule_members")
    op.execute("DROP TRIGGER IF EXISTS trg_delivery_addresses_normalize_email ON delivery_addresses")
    op.execute("DROP TRIGGER IF EXISTS trg_storage_purchases_no_truncate ON storage_purchases")
    op.execute("DROP TRIGGER IF EXISTS trg_unseal_events_no_truncate ON unseal_events")
    op.execute("DROP TRIGGER IF EXISTS trg_record_attachments_no_truncate ON record_attachments")
    op.execute("DROP TRIGGER IF EXISTS trg_record_attachments_no_delete ON record_attachments")
    op.execute("DROP TRIGGER IF EXISTS trg_record_attachments_no_update ON record_attachments")
    op.execute("DROP TRIGGER IF EXISTS trg_records_no_truncate ON records")
    op.execute("DROP TRIGGER IF EXISTS trg_records_no_delete ON records")
    op.execute("DROP TRIGGER IF EXISTS trg_records_no_update ON records")
    op.execute("DROP TRIGGER IF EXISTS trg_email_deliveries_updated_at ON email_deliveries")
    op.execute("DROP TRIGGER IF EXISTS trg_storage_usage_updated_at ON storage_usage")
    op.execute("DROP TRIGGER IF EXISTS trg_subscriptions_updated_at ON subscriptions")
    op.execute("DROP TRIGGER IF EXISTS trg_delivery_addresses_updated_at ON delivery_addresses")
    op.execute("DROP TRIGGER IF EXISTS trg_capsules_updated_at ON capsules")
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON users")

    # === 3. 関数 DROP ===
    op.execute("DROP FUNCTION IF EXISTS set_storage_purchases_expires_at()")
    op.execute("DROP FUNCTION IF EXISTS normalize_email_lower()")
    op.execute("DROP FUNCTION IF EXISTS update_storage_usage()")
    op.execute("DROP FUNCTION IF EXISTS prevent_records_mutation()")
    op.execute("DROP FUNCTION IF EXISTS trigger_set_updated_at()")

    # === 4. インデックス DROP ===
    op.execute("DROP INDEX IF EXISTS idx_email_deliveries_record_id")
    op.execute("DROP INDEX IF EXISTS idx_email_deliveries_delivery_address")
    op.execute("DROP INDEX IF EXISTS idx_email_deliveries_retry_candidates")
    op.execute("DROP INDEX IF EXISTS idx_email_deliveries_unseal_event_delivery")
    op.execute("DROP INDEX IF EXISTS idx_email_deliveries_capsule_id")
    op.execute("DROP INDEX IF EXISTS idx_unseal_events_notification_pending")
    op.execute("DROP INDEX IF EXISTS idx_unseal_events_capsule_id")
    op.execute("DROP INDEX IF EXISTS idx_storage_usage_capsule_id")
    op.execute("DROP INDEX IF EXISTS idx_storage_purchases_effective")
    op.execute("DROP INDEX IF EXISTS idx_storage_purchases_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_storage_purchases_user_id")
    op.execute("DROP INDEX IF EXISTS idx_storage_purchases_provider_txn")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_trial_end")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_status_active")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_google_token")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_apple_otxn")
    op.execute("DROP INDEX IF EXISTS idx_subscriptions_user_id")
    op.execute("DROP INDEX IF EXISTS idx_delivery_addresses_email_capsule")
    op.execute("DROP INDEX IF EXISTS idx_delivery_addresses_added_by")
    op.execute("DROP INDEX IF EXISTS idx_delivery_addresses_tag")
    op.execute("DROP INDEX IF EXISTS idx_delivery_addresses_is_active")
    op.execute("DROP INDEX IF EXISTS idx_delivery_addresses_capsule_id")
    op.execute("DROP INDEX IF EXISTS idx_record_attachments_record_id")
    op.execute("DROP INDEX IF EXISTS idx_records_capsule_posted")
    op.execute("DROP INDEX IF EXISTS idx_records_author_posted")
    op.execute("DROP INDEX IF EXISTS idx_records_capsule_window")
    op.execute("DROP INDEX IF EXISTS idx_capsule_members_active")
    op.execute("DROP INDEX IF EXISTS idx_capsule_members_capsule_email")
    op.execute("DROP INDEX IF EXISTS idx_capsule_members_user_id")
    op.execute("DROP INDEX IF EXISTS idx_capsule_members_capsule_id")
    op.execute("DROP INDEX IF EXISTS idx_capsules_open_at_unsealed")
    op.execute("DROP INDEX IF EXISTS idx_users_anonymize_scheduled_at")
    op.execute("DROP INDEX IF EXISTS idx_users_trial_ends_at")
    op.execute("DROP INDEX IF EXISTS idx_users_is_deleted")
    op.execute("DROP INDEX IF EXISTS idx_users_email")
    op.execute("DROP INDEX IF EXISTS idx_users_firebase_uid")

    # === 5. テーブル DROP（外部キー依存の逆順）===
    op.drop_table("record_attachments")
    op.drop_table("email_deliveries")
    op.drop_table("unseal_events")
    op.drop_table("storage_usage")
    op.drop_table("records")
    op.drop_table("delivery_addresses")
    op.drop_table("capsule_members")
    op.drop_table("subscriptions")
    op.drop_table("storage_purchases")
    op.drop_table("capsules")
    op.drop_table("users")

    # ロール / 拡張は残す（他プロジェクトと共有する可能性のため）
