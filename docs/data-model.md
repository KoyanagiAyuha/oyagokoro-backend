# おやごころ MVP データモデル設計書

> Neon PostgreSQL（PostgreSQL 16互換）/ 2026-07-03 / v1.2（IAP反映・仕様の穴3件追記・export_jobs 新設で12テーブル）

---

## 0. 概要

### テーブル構成

本MVPは **12テーブル** で構成される。

| # | テーブル名 | 役割区分 |
|---|-----------|---------|
| 1 | `users` | ユーザーマスター |
| 2 | `capsules` | タイムカプセル本体 |
| 3 | `capsule_members` | カプセル参加関係 |
| 4 | `records` | 投稿記録本文 |
| 5 | `record_attachments` | 添付ファイルメタデータ |
| 6 | `delivery_addresses` | 配信先メールアドレス |
| 7 | `subscriptions` | プラン契約状態（課金） |
| 8 | `storage_purchases` | 追加ストレージ購入履歴 |
| 9 | `storage_usage` | ストレージ使用量スナップショット |
| 10 | `unseal_events` | 開封イベントログ |
| 11 | `email_deliveries` | メール配信ログ |
| 12 | `export_jobs` | エクスポートジョブ状態（2026-07-03 追記） |

### 設計原則（共通指針）

1. **主キーは内部UUID**：外部公開しない。`gen_random_uuid()` で自動生成
2. **タイムスタンプはすべて TIMESTAMPTZ**：DBにはUTCで保存。表示はJST変換
3. **users 物理削除禁止**：論理削除（`is_deleted`）のみ。退会後は PII 匿名化（display_name / email / firebase_uid）で対応。records は永続保持（社会契約宣言）
4. **records は INSERT only**：保存後の変更・削除をDBトリガーで禁止。TRUNCATE 防御トリガーも追加（records / record_attachments / unseal_events / storage_purchases）
5. **状態管理に冗長カラムを持つ場合は明示**：`capsules.unsealed_at`（NULL=封印中）
6. **ストレージ集計はカプセル単位**：参加者の権限変更・削除に依存しない
7. **プランの真実は subscriptions、さらにその真実はストア側**：`subscriptions` は Apple / Google の購読状態のミラー。`users.current_plan` はそのキャッシュ
8. **外部キーの削除方針を明示**：RESTRICT / SET NULL / CASCADE を目的に応じて使い分け
9. **インデックスは部分インデックスを活用**：`WHERE` 条件で有効なレコードのみを対象
10. **課金は IAP（App Store / Google Play）**：Stripe は使用しない。顧客IDという概念自体が存在しないため、ユーザー↔購読の紐付けは購読識別子の逆引きで行う（詳細は §3.7・§4.7）

### 拠り所

`docs/product-spec.md`

---

## 1. ER図（Mermaid）

```mermaid
erDiagram
    users {
        UUID id PK
        TEXT firebase_uid UK
        TEXT email UK
        TEXT display_name
        TEXT locale
        TEXT timezone
        TEXT current_plan
        TIMESTAMPTZ trial_ends_at
        TIMESTAMPTZ terms_agreed_at
        TEXT terms_version
        BOOLEAN is_deleted
        TIMESTAMPTZ deleted_at
        TIMESTAMPTZ anonymize_scheduled_at
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    capsules {
        UUID id PK
        VARCHAR name
        TIMESTAMPTZ open_at
        TIMESTAMPTZ unsealed_at
        VARCHAR unseal_trigger
        UUID created_by FK
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    capsule_members {
        UUID id PK
        UUID capsule_id FK
        UUID user_id FK
        VARCHAR invited_email
        VARCHAR status
        TIMESTAMPTZ invited_at
        TEXT invite_token_hash
        TIMESTAMPTZ invite_token_expires_at
        TIMESTAMPTZ joined_at
        TIMESTAMPTZ deleted_at
        VARCHAR deletion_reason
        VARCHAR display_name_override
        TIMESTAMPTZ created_at
    }

    records {
        UUID id PK
        UUID capsule_id FK
        UUID author_id FK
        TEXT body
        TEXT visibility
        TIMESTAMPTZ posted_at
        TIMESTAMPTZ window_ends_at
        TIMESTAMPTZ created_at
    }

    record_attachments {
        UUID id PK
        UUID record_id FK
        TEXT attachment_type
        TEXT s3_object_key
        TEXT mime_type
        BIGINT byte_size
        TEXT original_filename
        INTEGER duration_seconds
        INTEGER width
        INTEGER height
        TIMESTAMPTZ created_at
    }

    delivery_addresses {
        UUID id PK
        UUID capsule_id FK
        VARCHAR email
        VARCHAR tag
        VARCHAR label
        BOOLEAN is_active
        UUID added_by FK
        TIMESTAMPTZ last_bounced_at
        INTEGER bounce_count
        VARCHAR paused_reason
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    subscriptions {
        UUID id PK
        UUID user_id FK
        TEXT plan_type
        TEXT status
        TEXT platform
        TEXT original_transaction_id
        TEXT purchase_token
        TEXT product_id
        TEXT environment
        TEXT latest_notification_type
        TIMESTAMPTZ latest_notification_at
        BOOLEAN auto_renew
        TIMESTAMPTZ current_period_start
        TIMESTAMPTZ current_period_end
        TIMESTAMPTZ trial_start
        TIMESTAMPTZ trial_end
        TIMESTAMPTZ cancel_at
        TIMESTAMPTZ canceled_at
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    storage_purchases {
        UUID id PK
        UUID user_id FK
        TEXT platform
        TEXT provider_transaction_id UK
        TEXT provider_order_id
        TEXT product_id
        TEXT environment
        INTEGER gb_added
        INTEGER price_jpy
        TIMESTAMPTZ purchased_at
        TIMESTAMPTZ expires_at
        TIMESTAMPTZ revoked_at
        TIMESTAMPTZ created_at
    }

    storage_usage {
        UUID id PK
        UUID capsule_id FK
        BIGINT used_bytes
        INTEGER attachment_count
        TIMESTAMPTZ last_calculated_at
        TIMESTAMPTZ updated_at
    }

    unseal_events {
        UUID id PK
        UUID capsule_id FK
        VARCHAR trigger_type
        UUID executed_by FK
        TIMESTAMPTZ executed_at
        TIMESTAMPTZ notification_sent_at
        TIMESTAMPTZ created_at
    }

    email_deliveries {
        UUID id PK
        UUID capsule_id FK
        UUID record_id FK
        UUID delivery_address_id FK
        UUID unseal_event_id FK_NULL
        VARCHAR email_type
        VARCHAR resend_message_id
        VARCHAR status
        SMALLINT attempt_count
        TIMESTAMPTZ last_attempted_at
        TEXT error_message
        VARCHAR skipped_reason
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    export_jobs {
        UUID id PK
        UUID capsule_id FK
        UUID requested_by FK
        TEXT status
        TEXT scope
        TEXT_ARRAY formats
        JSONB object_keys
        TEXT error_message
        TIMESTAMPTZ requested_at
        TIMESTAMPTZ completed_at
        TIMESTAMPTZ expires_at
    }

    users ||--o{ capsules : "created_by（創設者）"
    users ||--o{ capsule_members : "user_id（参加）"
    users ||--o{ records : "author_id（投稿）"
    users ||--o{ delivery_addresses : "added_by（追加者）"
    users ||--o| subscriptions : "user_id（0 or 1）"
    users ||--o{ storage_purchases : "user_id（購入）"
    users ||--o{ unseal_events : "executes（開封実行者）"
    users ||--o{ export_jobs : "requested_by（エクスポート要求者）"

    capsules ||--o{ capsule_members : "capsule_id（参加関係）"
    capsules ||--o{ records : "capsule_id（記録）"
    capsules ||--o{ delivery_addresses : "capsule_id（配信先）"
    capsules ||--o{ storage_usage : "capsule_id（使用量）"
    capsules ||--o{ unseal_events : "capsule_id（開封）"
    capsules ||--o{ email_deliveries : "capsule_id（配信ログ）"
    capsules ||--o{ export_jobs : "capsule_id（エクスポート対象）"

    records ||--o{ record_attachments : "record_id（添付）"
    records ||--o{ email_deliveries : "record_id（配信ログ）"

    delivery_addresses ||--o{ email_deliveries : "delivery_address_id（配信先）"

    unseal_events ||--o{ email_deliveries : "unseal_event_id（配信紐付け）"
```

> `export_jobs.formats` は Mermaid の型表記制約上 `TEXT_ARRAY` と表記しているが、実 DDL は `TEXT[]` を用いる（§3.12）。

---

## 2. テーブル一覧と責務

| テーブル | 責務 | 主キー | 主要外部キー |
|---------|------|--------|------------|
| `users` | Firebase Auth認証ユーザーのプロファイル・プラン状態・論理削除管理 | `id` (UUID) | — |
| `capsules` | タイムカプセル本体。開封日・封印状態・創設者を管理 | `id` (UUID) | `created_by → users.id` |
| `capsule_members` | カプセルへの参加関係（招待中/アクティブ/削除済み）を管理 | `id` (UUID) | `capsule_id → capsules.id`, `user_id → users.id` |
| `records` | タイムカプセルへの投稿本文。INSERT only・1週間ウィンドウを管理 | `id` (UUID) | `capsule_id → capsules.id`, `author_id → users.id` |
| `record_attachments` | 記録に紐付く画像・音声ファイルのS3参照メタデータ | `id` (UUID) | `record_id → records.id` |
| `delivery_addresses` | 開封時の記録配信先メールアドレスとタグ・バウンス状態を管理 | `id` (UUID) | `capsule_id → capsules.id`, `added_by → users.id` |
| `subscriptions` | プラン契約状態の真実の源（Apple/Google ストア購読状態のミラー、1ユーザー1行） | `id` (UUID) | `user_id → users.id` |
| `storage_purchases` | 追加ストレージ買い切り購入履歴（原則不変。返金時のみ `revoked_at` を更新） | `id` (UUID) | `user_id → users.id` |
| `storage_usage` | カプセル単位のストレージ使用量スナップショット（即時更新） | `id` (UUID) | `capsule_id → capsules.id` |
| `unseal_events` | タイムカプセル開封イベントの記録（INSERT only・不可逆） | `id` (UUID) | `capsule_id → capsules.id`, `executed_by → users(id) ON DELETE SET NULL` |
| `email_deliveries` | メール配信ログ（通知・記録配信・リトライ管理） | `id` (UUID) | `capsule_id → capsules.id`, `record_id → records.id`, `delivery_address_id → delivery_addresses.id`, `unseal_event_id → unseal_events.id` |
| `export_jobs` | 非同期データエクスポート（api-spec §6.4/§6.5）のジョブ状態永続化。要求者・生成物 S3 キー・失敗理由・有効期限を管理（2026-07-03 追記） | `id` (UUID) | `capsule_id → capsules.id`, `requested_by → users.id` |

---

## 3. 各テーブル詳細

### 3.1 users

**責務**: Firebase Auth で認証されたユーザーのプロファイルおよびサービス利用状態を管理するマスターテーブル。プラン状態・トライアル有効期限・利用規約同意・論理削除・データパージスケジュールを一元保持し、アプリ全体の認可・課金・配信可否判定の起点となる。

#### カラム定義

| カラム | 型 | 制約 | 説明 |
|--------|-----|------|------|
| `id` | `UUID` | PRIMARY KEY, DEFAULT gen_random_uuid() | 内部主キー。外部公開しない |
| `firebase_uid` | `TEXT` | UNIQUE NOT NULL | Firebase Auth が発行するユーザー識別子。認証連携の唯一の外部キー |
| `email` | `TEXT` | UNIQUE NOT NULL | ログイン用メールアドレス（Firebase Auth と同期。Magic Link の送信先） |
| `display_name` | `TEXT` | | アプリ内表示名。未設定可（オンボーディングで後付け） |
| `locale` | `TEXT` | NOT NULL DEFAULT 'ja' | UI 表示言語（BCP-47 タグ例: 'ja', 'en-US'） |
| `timezone` | `TEXT` | NOT NULL DEFAULT 'Asia/Tokyo' | ユーザータイムゾーン（IANA tz DB 形式）。1週間ウィンドウ表示の変換基準 |
| `current_plan` | `TEXT` | NOT NULL DEFAULT 'free' | プランキャッシュ値（'free' / 'paid_monthly' / 'paid_yearly'）。真実の源は `subscriptions`（さらにその真実はストア側） |
| `trial_ends_at` | `TIMESTAMPTZ` | | 7日間無料トライアル終了日時のキャッシュ（`subscriptions.trial_end` のミラー）。NULL = トライアル未使用または終了済み |
| `terms_agreed_at` | `TIMESTAMPTZ` | | 最新の利用規約同意日時。NULL = 未同意（サービス利用不可） |
| `terms_version` | `TEXT` | | 同意した利用規約バージョン文字列（例: '2026-05-26'）。バージョンアップ時に再同意を要求する |
| `is_deleted` | `BOOLEAN` | NOT NULL DEFAULT FALSE | 論理削除フラグ。TRUE = 退会済み（物理削除禁止） |
| `deleted_at` | `TIMESTAMPTZ` | | 論理削除実行日時。is_deleted=TRUE の場合に必ず設定 |
| `anonymize_scheduled_at` | `TIMESTAMPTZ` | | PII 匿名化スケジュール日時。退会後5年を目安に設定。匿名化対象: display_name / email / firebase_uid を NULL またはプレースホルダ値に置換 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | レコード作成日時 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL DEFAULT NOW() | レコード最終更新日時（UPDATE トリガーで自動更新） |

#### IAP 課金における users の位置づけ

IAP には Stripe の `customer` に相当する「顧客ID」概念が存在しない。そのため `users` に決済プロバイダの顧客IDカラムは持たない。ユーザー↔購読の紐付けは以下の方式で行う：

- 購入時にアプリが `users.id`（UUID）をそのまま購入トークンとして渡す。Apple では `appAccountToken`、Google では `obfuscatedExternalAccountId` に設定する
- `users.id` 自体が UUID であるため、専用の紐付けカラム（例: `app_account_token`）を新設する必要はない（冗長カラムを増やさない）
- ただしこのトークンはクライアント供給かつ任意で、リストア購入やサーバ通知経由では欠落し得るため、紐付けの権威にはしない。権威は `subscriptions` 側の購読識別子（`original_transaction_id` / `purchase_token`）から `user_id` を逆引きする経路に置く。トークンはあくまで初回購入時の紐付けヒント（詳細は §3.7・§4.7）

#### インデックス

```sql
CREATE UNIQUE INDEX idx_users_firebase_uid ON users (firebase_uid);
CREATE UNIQUE INDEX idx_users_email ON users (email);
CREATE INDEX idx_users_is_deleted ON users (is_deleted)
    WHERE is_deleted = FALSE;
CREATE INDEX idx_users_trial_ends_at ON users (trial_ends_at)
    WHERE trial_ends_at IS NOT NULL AND is_deleted = FALSE;
CREATE INDEX idx_users_anonymize_scheduled_at ON users (anonymize_scheduled_at)
    WHERE anonymize_scheduled_at IS NOT NULL;
```

#### CHECK 制約

- `current_plan IN ('free', 'paid_monthly', 'paid_yearly')`
- `is_deleted = FALSE OR deleted_at IS NOT NULL`（論理削除の整合性）
- `(terms_agreed_at IS NULL AND terms_version IS NULL) OR (terms_agreed_at IS NOT NULL AND terms_version IS NOT NULL)`（同意カラムの整合性）

---

### 3.2 capsules

**責務**: タイムカプセル（グループ）の本体。開封日・封印状態・創設者・凍結状態を一元管理する。1グループ = 1レコード。

#### カラム定義

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|---------|------|
| `id` | `UUID` | NOT NULL | `gen_random_uuid()` | 内部主キー |
| `name` | `VARCHAR(255)` | NOT NULL | — | カプセル名（例: 「田中家のタイムカプセル」） |
| `open_at` | `TIMESTAMPTZ` | NOT NULL | — | 開封日（初回セットアップで必須入力、スキップ不可） |
| `unsealed_at` | `TIMESTAMPTZ` | NULL | `NULL` | 開封実施日時。NULL = 封印中、値あり = 開封済み |
| `unseal_trigger` | `VARCHAR(20)` | NULL | `NULL` | 開封トリガー。`'manual'`（任意開封）/ `'scheduled'`（開封日自動開封）。封印中は NULL |
| `created_by` | `UUID` | NOT NULL | — | 創設者の `users.id`（FK） |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | 作成日時 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | 最終更新日時 |

#### インデックス

```sql
-- 開封日スケジューラーが毎日未開封カプセルをポーリング
CREATE INDEX idx_capsules_open_at_unsealed
    ON capsules (open_at)
    WHERE unsealed_at IS NULL;
```

#### CHECK 制約

- `unseal_trigger IN ('manual', 'scheduled')`
- `(unsealed_at IS NULL AND unseal_trigger IS NULL) OR (unsealed_at IS NOT NULL AND unseal_trigger IS NOT NULL)`（封印状態の整合性）

#### 外部キー

- `created_by → users(id) ON DELETE RESTRICT`

#### 補足

- `open_at` は参加者全員が変更可能。開封済み後は変更不可
- 凍結状態は `capsule_members` の `active` 件数 = 0 をクエリで判定。`capsules` に凍結フラグは持たない

---

### 3.3 capsule_members

**責務**: タイムカプセルへの参加関係を管理する。招待中・アクティブ・削除済みの状態遷移と、削除参加者の「元参加者」表記制御に必要な情報を保持する。

#### カラム定義

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|---------|------|
| `id` | `UUID` | NOT NULL | `gen_random_uuid()` | 内部主キー |
| `capsule_id` | `UUID` | NOT NULL | — | 所属カプセルの `capsules.id` FK |
| `user_id` | `UUID` | NULL | `NULL` | 参加ユーザーの `users.id` FK（招待受諾前は NULL） |
| `invited_email` | `VARCHAR(320)` | NOT NULL | — | 招待先メールアドレス（参加後も保持） |
| `status` | `VARCHAR(20)` | NOT NULL | `'invited'` | 参加状態（'invited' / 'active' / 'deleted'） |
| `invited_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | 招待送信日時 |
| `invite_token_hash` | `TEXT` | NULL | `NULL` | 招待受諾用の不透明トークンの SHA-256 等ハッシュ値。生トークンはDBに保存しない（招待作成時に一度だけ生成し、招待メール本文・招待作成APIレスポンスでのみ提示）。`status='invited'` の行でのみ非NULL、`'active'`/`'deleted'` への遷移時に `NULL` へクリアする（2026-07-03 追記） |
| `invite_token_expires_at` | `TIMESTAMPTZ` | NULL | `NULL` | 招待トークンの有効期限。`status='invited'` の行でのみ非NULL、`'active'`/`'deleted'` への遷移時に `NULL` へクリアする（2026-07-03 追記） |
| `joined_at` | `TIMESTAMPTZ` | NULL | `NULL` | 招待承諾・参加完了日時（アクティブ転換時に記録） |
| `deleted_at` | `TIMESTAMPTZ` | NULL | `NULL` | 削除日時（退出 or 他参加者による削除） |
| `deletion_reason` | `VARCHAR(50)` | NULL | `NULL` | 削除区分: `'self_exit'`（自己退出）/ `'removed_by_member'`（他参加者による削除） |
| `display_name_override` | `VARCHAR(255)` | NULL | `NULL` | 削除後の表示名スナップショット（元参加者表記用） |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | レコード作成日時 |

#### status 値と遷移

| 値 | 意味 | 遷移条件 |
|---|------|---------|
| `'invited'` | 招待送信済み・未承諾 | 初期値 |
| `'active'` | アクティブ参加者。全機能利用可 | 招待リンクから参加完了時（`joined_at` も記録） |
| `'deleted'` | 削除済み。アクセス不可。記録は「元参加者」表記で保持 | 自己退出 or 他参加者による削除 |

#### 招待トークンの運用（2026-07-03 追記）

- 招待作成時（`POST /capsules/{capsuleId}/members`、api-spec §4.2）に、サーバーが不透明な生トークン（十分なエントロピーを持つランダム文字列）を一度だけ生成する。生トークンは招待作成APIのレスポンスと招待メール本文の受諾リンクにのみ含め、DBには保存しない
- DBには生トークンの SHA-256 等によるハッシュ値のみを `invite_token_hash` に保存する。招待受諾API（`POST /invitations/{token}/accept`、api-spec §4.4）は受け取った `token` をハッシュ化し、`invite_token_hash` と突合して照合する
- `invite_token_expires_at` で有効期限を管理する。期限切れ・ハッシュ不一致のいずれも `404 ERR_INVITATION_NOT_FOUND`（存在秘匿。api-spec §4.4）として扱う
- 受諾成功（`status='active'` への遷移）または参加者削除（`status='deleted'` への遷移）の際、`invite_token_hash` / `invite_token_expires_at` は共に `NULL` にクリアする（`chk_capsule_members_invite_token_status` で強制。下記CHECK制約参照）

#### インデックス

```sql
-- カプセル内の参加者一覧取得
CREATE INDEX idx_capsule_members_capsule_id ON capsule_members (capsule_id);
-- ユーザーが参加しているカプセル一覧取得
CREATE INDEX idx_capsule_members_user_id ON capsule_members (user_id)
    WHERE user_id IS NOT NULL;
-- 招待メアドによる重複招待防止・参加照合
-- invited_email は LOWER() で正規化し UNIQUE INDEX を張る（大文字小文字の違いによる重複登録を防ぐ）
CREATE UNIQUE INDEX idx_capsule_members_capsule_email
    ON capsule_members (capsule_id, LOWER(invited_email));
-- アクティブ参加者のみに絞り込む（凍結状態判定・開封後追加禁止チェック）
CREATE INDEX idx_capsule_members_active
    ON capsule_members (capsule_id, status)
    WHERE status = 'active';
-- 招待受諾時のトークン照合（POST /invitations/{token}/accept）（2026-07-03 追記）
-- 生トークンはDBに保存しないため、受諾APIはリクエストのtokenをハッシュ化してこの索引で照合する
CREATE INDEX idx_capsule_members_invite_token_hash
    ON capsule_members (invite_token_hash)
    WHERE invite_token_hash IS NOT NULL;
```

#### CHECK 制約

- `status IN ('invited', 'active', 'deleted')`
- `deletion_reason IN ('self_exit', 'removed_by_member')`
- `(status = 'deleted' AND deleted_at IS NOT NULL AND deletion_reason IS NOT NULL) OR (status != 'deleted' AND deleted_at IS NULL AND deletion_reason IS NULL)`
- `(status = 'active' AND joined_at IS NOT NULL) OR (status != 'active')`
- `chk_capsule_members_invite_token_status`（2026-07-03 追記）: `status != 'invited'` の行は招待トークンを保持しない（受諾・削除確定後はトークンをクリアする）:
  ```sql
  (status = 'invited') OR (invite_token_hash IS NULL AND invite_token_expires_at IS NULL)
  ```
- `chk_capsule_members_invite_token_pair`（2026-07-03 追記）: `invite_token_hash` と `invite_token_expires_at` は両方 NULL か両方非NULLのいずれか（片方だけの設定を禁止）:
  ```sql
  (invite_token_hash IS NULL) = (invite_token_expires_at IS NULL)
  ```

#### 外部キー

- `capsule_id → capsules(id) ON DELETE RESTRICT`
- `user_id → users(id) ON DELETE RESTRICT`

---

### 3.4 records

**責務**: タイムカプセルへの投稿本文を管理する。1件の記録は1人の参加者が1回書いたテキスト（および任意の添付を持つ）。保存後は内容変更・削除を禁止する。1週間ウィンドウ（`window_ends_at`）と `visibility` によって、封印モード中の他参加者への表示可否を制御する。

#### カラム定義

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---------|-----|---------|---------|------|
| `id` | UUID | YES | `gen_random_uuid()` | 内部主キー |
| `capsule_id` | UUID | YES | — | 所属タイムカプセル（capsules.id への FK） |
| `author_id` | UUID | YES | — | 投稿者（users.id への FK） |
| `body` | TEXT | YES | — | 本文。最大5,000字（CHECK制約で強制） |
| `visibility` | TEXT | YES | `'all'` | 届け先区分。`'all'` または `'parents_only'`（CHECK制約） |
| `posted_at` | TIMESTAMPTZ | YES | `NOW()` | 投稿完了日時。ウィンドウ計算の起点 |
| `window_ends_at` | TIMESTAMPTZ | YES | — | 1週間ウィンドウ終了日時（投稿日翌日0時JST起算で7日間）。`GENERATED ALWAYS AS` 生成列として自動計算（トリガー不要・常に整合性が保たれる）。PostgreSQL 16 の `GENERATED ALWAYS AS` は immutable 関数のみ使用可能なため、`AT TIME ZONE` 演算子ではなく `timezone(text, timestamptz)` 関数形式で実装する |
| `created_at` | TIMESTAMPTZ | YES | `NOW()` | レコード作成日時 |

#### インデックス

```sql
-- 封印モードアーカイブの主クエリ
CREATE INDEX idx_records_capsule_window
    ON records (capsule_id, window_ends_at)
    WHERE window_ends_at IS NOT NULL;

-- 月次件数集計・時系列一覧
CREATE INDEX idx_records_author_posted
    ON records (author_id, posted_at DESC);

-- タイムカプセル内の時系列ソート
CREATE INDEX idx_records_capsule_posted
    ON records (capsule_id, posted_at DESC);
```

#### CHECK 制約

- `char_length(body) BETWEEN 1 AND 5000`
- `visibility IN ('all', 'parents_only')`
- `window_ends_at > posted_at`

#### 外部キー

- `author_id → users(id) ON UPDATE CASCADE ON DELETE RESTRICT`
- `capsule_id → capsules(id) ON UPDATE CASCADE ON DELETE RESTRICT`

#### トリガー

- **`window_ends_at` は GENERATED ALWAYS 生成列**: トリガーではなく生成列として定義。`posted_at` の変更があれば DB が自動で再計算するため、アプリ層の計算ミスが入り込む余地がない。PostgreSQL 16 の `GENERATED ALWAYS AS` は immutable 関数のみ使用可能なため、`AT TIME ZONE` 演算子の代わりに `timezone(text, timestamptz)` 関数形式（immutable）で記述する
- **UPDATE / DELETE 時**: `prevent_records_mutation()` トリガーで即時エラー（INSERT only 強制）

---

### 3.5 record_attachments

**責務**: 記録に紐付く画像・音声ファイルのS3参照メタデータを管理する。実バイナリはS3に保存し、DBにはオブジェクトキーとメタ情報のみ保持する。ストレージ消費量の集計（`byte_size` の合計）にも使用する。

#### カラム定義

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---------|-----|---------|---------|------|
| `id` | UUID | YES | `gen_random_uuid()` | 内部主キー |
| `record_id` | UUID | YES | — | 親記録（records.id への FK） |
| `attachment_type` | TEXT | YES | — | 添付種別。`'image'` または `'audio'`（CHECK制約） |
| `s3_object_key` | TEXT | YES | — | S3オブジェクトキー（`attachments/{capsule_id}/{record_id}/{id}.{ext}` 命名規約） |
| `mime_type` | TEXT | YES | — | MIMEタイプ（例: `image/webp`、`audio/mpeg`） |
| `byte_size` | BIGINT | YES | — | 実バイト数。ストレージ集計に使用 |
| `original_filename` | TEXT | NO | NULL | アップロード元ファイル名（表示用。必須ではない） |
| `duration_seconds` | INTEGER | NO | NULL | 音声の長さ（秒）。`attachment_type = 'audio'` の時のみ設定 |
| `width` | INTEGER | NO | NULL | 画像の幅（px）。`attachment_type = 'image'` の時のみ設定 |
| `height` | INTEGER | NO | NULL | 画像の高さ（px）。`attachment_type = 'image'` の時のみ設定 |
| `created_at` | TIMESTAMPTZ | YES | `NOW()` | レコード作成日時 |

#### インデックス

```sql
-- 記録に紐付く添付一覧（最頻出クエリ）
CREATE INDEX idx_record_attachments_record_id
    ON record_attachments (record_id);
```

#### CHECK 制約

- `attachment_type IN ('image', 'audio')`
- `byte_size > 0`
- `(attachment_type = 'audio' AND duration_seconds IS NOT NULL) OR (attachment_type = 'image' AND duration_seconds IS NULL)`（音声のみ duration）
- `(attachment_type = 'image' AND width IS NOT NULL AND height IS NOT NULL) OR (attachment_type = 'audio' AND width IS NULL AND height IS NULL)`（画像のみ寸法）
- `char_length(s3_object_key) > 0`

#### 外部キー

- `record_id → records(id) ON UPDATE CASCADE ON DELETE RESTRICT`

#### トリガー

- INSERT 時に `update_storage_usage()` トリガーが `storage_usage` テーブルを即時 UPSERT 更新

---

### 3.6 delivery_addresses

**責務**: タイムカプセル開封時に記録を配信するメールアドレスリストを管理する。タグによる配信フィルタ、バウンス管理、削除参加者メアドの自動削除を担う。

#### カラム定義

| カラム | 型 | 制約 | デフォルト | 説明 |
|--------|-----|------|---------|------|
| `id` | UUID | PRIMARY KEY | `gen_random_uuid()` | 配信先レコード一意識別子 |
| `capsule_id` | UUID | FK → capsules(id) ON DELETE CASCADE | — | 所属するタイムカプセル |
| `email` | VARCHAR(254) | NOT NULL | — | 配信先メールアドレス（RFC 5321準拠、最大254字） |
| `tag` | VARCHAR(20) | NOT NULL, CHECK IN ('all', 'parents_only') | `'all'` | 配信対象フィルタタグ。`all`: 全記録対象、`parents_only`: 「内輪のみ」記録のみ配信対象 |
| `label` | VARCHAR(100) | — | NULL | ユーザー向け表示名（例: 「娘のメアド」「夫」、オプション） |
| `is_active` | BOOLEAN | NOT NULL | `true` | バウンス状態フラグ。`false` 時は配信対象から除外 |
| `added_by` | UUID | FK → users(id) ON DELETE SET NULL | — | このメアドを追加した参加者ID。参加者削除時の自動削除判定に使用 |
| `last_bounced_at` | TIMESTAMPTZ | — | NULL | 最後にバウンスを検知した日時 |
| `bounce_count` | INTEGER | NOT NULL | `0` | バウンス回数カウンター |
| `paused_reason` | VARCHAR(200) | — | NULL | is_active = false になった理由（`'bounce'` / `'user_requested'` など） |
| `created_at` | TIMESTAMPTZ | NOT NULL | `CURRENT_TIMESTAMP` | メアド登録日時 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `CURRENT_TIMESTAMP` | 最終更新日時 |

#### インデックス

```sql
CREATE INDEX idx_delivery_addresses_capsule_id ON delivery_addresses(capsule_id);
-- 同一capsule内でのメアド重複防止（UNIQUE制約）
-- email は LOWER() で正規化し UNIQUE INDEX を張る（大文字小文字の違いによる重複登録・重複配信を防ぐ）
-- INSERT 時はアプリ層 or BEFORE INSERT トリガーで email = LOWER(email) への正規化を必須とする
CREATE UNIQUE INDEX idx_delivery_addresses_email_capsule
    ON delivery_addresses(capsule_id, LOWER(email));
-- 配信時に is_active = true のメアドのみフィルタ
CREATE INDEX idx_delivery_addresses_is_active
    ON delivery_addresses(capsule_id, is_active)
    WHERE is_active = true;
-- タグフィルタ検索（「内輪のみ」記録配信時）
CREATE INDEX idx_delivery_addresses_tag ON delivery_addresses(capsule_id, tag);
-- 参加者削除時の関連メアド検索
CREATE INDEX idx_delivery_addresses_added_by ON delivery_addresses(added_by);
```

#### 外部キー

- `capsule_id → capsules(id) ON DELETE CASCADE`（カプセル削除時に配信先も自動削除）
- `added_by → users(id) ON DELETE SET NULL`

---

### 3.7 subscriptions

**責務**: ユーザーのプラン契約状態の真実の源（source of truth）——ただし、その真実は Apple App Store / Google Play ストア側にある。当方 DB は Server-to-Server 通知（Apple App Store Server Notifications V2 / Google Real-time Developer Notifications）と検証 API から取得した購読状態のミラーである。トライアル期間・解約予定・有効期間を管理する。`users.current_plan` はここの値をさらに非正規化したキャッシュに過ぎない。

IAP には Stripe の `customer` / `subscription` に相当する単一 ID がない。Apple と Google では購読識別子のライフサイクルが根本的に異なるため（Apple `originalTransactionId` は購読の一生を通じて不変、Google `purchaseToken` は再購読・アップグレード時にローテーションする）、両者を単一カラムに混在させず、プラットフォーム別の専用カラムとして分離する（後述）。

#### カラム定義

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|---------|------|
| `id` | `UUID` | NOT NULL | `gen_random_uuid()` | 内部主キー |
| `user_id` | `UUID` | NOT NULL | — | `users.id` への外部キー（`UNIQUE (user_id)` で1ユーザー1レコードを強制） |
| `plan_type` | `TEXT` | NOT NULL | — | `'free'` / `'paid_monthly'` / `'paid_yearly'` |
| `status` | `TEXT` | NOT NULL | — | `'trialing'` / `'active'` / `'in_grace_period'` / `'canceled'` / `'on_hold'` / `'expired'`（詳細は下記） |
| `platform` | `TEXT` | NULL | `NULL` | `'apple'` / `'google'`。無料プランは NULL |
| `original_transaction_id` | `TEXT` | NULL | `NULL` | Apple の購読不変キー（`originalTransactionId`）。購読の一生を通じて不変。無料プラン/Google は NULL |
| `purchase_token` | `TEXT` | NULL | `NULL` | Google の最新 `purchaseToken`。再購読・アップグレード時にローテーションするため、都度最新値へ UPDATE する。無料プラン/Apple は NULL |
| `product_id` | `TEXT` | NULL | `NULL` | ストア商品ID（例: `com.lydear.oyagokoro.premium.monthly` / `premium_yearly`）。無料プランは NULL |
| `environment` | `TEXT` | NULL | `NULL` | `'sandbox'` / `'production'`。エンタイトルメント判定・sandbox/production 混線防止に使用 |
| `latest_notification_type` | `TEXT` | NULL | `NULL` | 直近通知種別（Apple `notificationType`+`subtype` / Google `notificationType` 数値）。監査・デバッグ用 |
| `latest_notification_at` | `TIMESTAMPTZ` | NULL | `NULL` | 直近通知の発生時刻（Apple `signedDate` / Google 取得状態の `eventTime`）。通知の順序保証・冪等 UPSERT の要（§4.7） |
| `auto_renew` | `BOOLEAN` | NULL | `NULL` | 自動更新 ON/OFF。`false` かつ期限内 = 解約予定の判定に使用 |
| `current_period_start` | `TIMESTAMPTZ` | NULL | `NULL` | 現在の請求期間開始（無料プランは NULL） |
| `current_period_end` | `TIMESTAMPTZ` | NULL | `NULL` | 現在の請求期間終了 = 次回更新日。Apple は最新 renewal の署名付き transaction の `expiresDate`、Google は `purchases.subscriptionsv2.get` の `lineItems[].expiryTime` から取得（無料プランは NULL） |
| `trial_start` | `TIMESTAMPTZ` | NULL | `NULL` | トライアル開始日時（トライアル未使用は NULL）。ストアの導入オファー情報から導出 |
| `trial_end` | `TIMESTAMPTZ` | NULL | `NULL` | トライアル終了日時。トライアルの時計はストアが持つため、当方は取得値を保存するのみ。`users.trial_ends_at` はこのミラー |
| `cancel_at` | `TIMESTAMPTZ` | NULL | `NULL` | 解約予定日時。`auto_renew = false` かつ期限内の場合に `current_period_end` と同値を設定 |
| `canceled_at` | `TIMESTAMPTZ` | NULL | `NULL` | 実際に権利を喪失した日時 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | レコード作成日時 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | レコード更新日時（Apple ASSN V2 / Google RTDN 受信ごとに更新） |

#### 識別子カラム設計の根拠（プラットフォーム別カラム方式）

- **採用方式**: Apple 用（`original_transaction_id`）と Google 用（`purchase_token`）を別カラムに分離する（汎用 `provider_subscription_id` 単一列 + `platform` 判別方式は採用しない）
- **根拠**: Apple の識別子は不変、Google はローテーションするというライフサイクルの違いが根本的であるため、単一カラムに混在させると型安全な UPDATE が書けず、プラットフォーム別 UNIQUE の意味も曖昧になる。別カラムであれば「Google 側だけ最新トークンに UPDATE」が明確に書け、下流の API・製品仕様も名前で参照できる
- NULL 列が2本増えるトレードオフは、下記 CHECK 制約（`subscriptions_provider_identifier_consistency`）でプラットフォームと識別子の整合をDB層で強制することで担保する

#### status 値とエンタイトルメント判定

```
status IN ('trialing', 'active', 'in_grace_period', 'canceled', 'on_hold', 'expired')
```

- **エンタイトルメント（有料機能を使える）判定ルール**: `status IN ('trialing', 'active', 'in_grace_period')` は無条件で権利あり。`status = 'canceled'` は `current_period_end > now()` の間だけ権利あり（期限まで利用継続）。`on_hold` / `expired` は権利なし → `users.current_plan = 'free'` にキャッシュを落とす
- `in_grace_period`（猶予期間・権利あり）と `on_hold`（決済リトライ中・権利なし）を明確に分離する。猶予中はサービス継続、`on_hold` で無料プラン相当に落とす。時計（猶予期間の長さ等）はストアが管理する

**両ストア通知からの導出マッピング表**:

| 当方 status | Apple（notificationType / subtype・状態） | Google（subscriptionState / notificationType） |
|-------------|------------------------------------------|-----------------------------------------------|
| `trialing` | `SUBSCRIBED`（subtype `INITIAL_BUY`）かつ導入オファー=無料期間中 | `SUBSCRIPTION_STATE_ACTIVE` かつ `paymentState`=free trial |
| `active` | `SUBSCRIBED` / `DID_RENEW` / `DID_CHANGE_RENEWAL_PREF`（有効・課金済み） | `SUBSCRIPTION_STATE_ACTIVE`（trial 以外） |
| `in_grace_period` | `DID_FAIL_TO_RENEW`（subtype `GRACE_PERIOD`） | `SUBSCRIPTION_STATE_IN_GRACE_PERIOD` |
| `canceled` | `DID_CHANGE_RENEWAL_STATUS`（subtype `AUTO_RENEW_DISABLED`。期限内・auto_renew=false） | `SUBSCRIPTION_STATE_CANCELED`（`autoRenewing=false`・期限内） |
| `on_hold` | `DID_FAIL_TO_RENEW`（grace 経過・billing retry 中で権利なし） | `SUBSCRIPTION_STATE_ON_HOLD` / `_PAUSED` |
| `expired` | `EXPIRED` / `GRACE_PERIOD_EXPIRED` | `SUBSCRIPTION_STATE_EXPIRED` |
| `expired`（返金起因） | `REFUND`（返金確定 → 権利剥奪） | `VOIDED_PURCHASE`（サブスク） |

> Google RTDN の通知本文は購読状態そのものを含まないため、通知受信時は必ず `purchases.subscriptionsv2.get` を叩いて `subscriptionState` を取得し、上表右列の状態から status を確定する（通知本文だけで status を決めない）。

#### インデックス

```sql
-- 1 ユーザー 1 購読
CREATE UNIQUE INDEX idx_subscriptions_user_id ON subscriptions (user_id);

-- プラットフォーム別 部分UNIQUE（識別子の重複購読防止・冪等UPSERTのキー）
CREATE UNIQUE INDEX idx_subscriptions_apple_otxn
    ON subscriptions (original_transaction_id)
    WHERE original_transaction_id IS NOT NULL;
CREATE UNIQUE INDEX idx_subscriptions_google_token
    ON subscriptions (purchase_token)
    WHERE purchase_token IS NOT NULL;

-- 有効購読の絞り込み（エンタイトルメント・バッチ）
CREATE INDEX idx_subscriptions_status_active ON subscriptions (status)
    WHERE status IN ('trialing', 'active', 'in_grace_period', 'canceled');

-- トライアル終了バッチ
CREATE INDEX idx_subscriptions_trial_end ON subscriptions (trial_end)
    WHERE trial_end IS NOT NULL;
```

#### CHECK 制約

- `plan_type IN ('free', 'paid_monthly', 'paid_yearly')`
- `status IN ('trialing', 'active', 'in_grace_period', 'canceled', 'on_hold', 'expired')`
- `platform IS NULL OR platform IN ('apple', 'google')`
- `environment IS NULL OR environment IN ('sandbox', 'production')`
- `subscriptions_provider_identifier_consistency`（プラットフォームと識別子の整合。NULL 許容カラムの濫用を防ぐ、§4.5.1 の email_deliveries と同じ流儀）:
  ```sql
  (plan_type = 'free'  AND platform IS NULL
     AND original_transaction_id IS NULL AND purchase_token IS NULL)
  OR (platform = 'apple'  AND original_transaction_id IS NOT NULL AND purchase_token IS NULL)
  OR (platform = 'google' AND purchase_token IS NOT NULL AND original_transaction_id IS NULL)
  ```

> `environment` は UNIQUE キーに含めない。Apple `originalTransactionId` は sandbox/production で名前空間が分離され実質衝突しないため。ただし本番エンタイトルメント判定では `environment = 'production'` を要求し、sandbox 購入が本番権利を付与しないようアプリ層でガードする。

#### 外部キー

- `user_id → users(id) ON DELETE RESTRICT`

#### 無料プラン行の扱い

`plan_type = 'free'` の行は `platform` / `original_transaction_id` / `purchase_token` すべて NULL（CHECK で強制）。トライアル開始時などの free → paid 遷移では、`UNIQUE (user_id)` により新規行は作らず、既存の1行を UPDATE する運用とする。

---

### 3.8 storage_purchases

**責務**: 追加ストレージの買い切り（消費型 IAP）購入履歴。1件 = 10GB 追加 × 1,500円。原則不変・20年保管期限を `expires_at` で持つ。ただし消費型 IAP は Apple `REFUND` / Google `VOIDED_PURCHASE` による返金が現実に起こり得るため、返金時のみ `revoked_at` の更新を許可する（§7 相当の設計判断、下記「immutability の方針」参照）。

#### カラム定義

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---------|-----|---------|---------|------|
| `id` | `UUID` | YES | `gen_random_uuid()` | 内部主キー |
| `user_id` | `UUID` | YES | — | `users.id` への外部キー |
| `platform` | `TEXT` | YES | — | `'apple'` / `'google'` |
| `provider_transaction_id` | `TEXT` | YES | — | 冪等キー。Apple = `transactionId`（購入ごとに一意）/ Google = `purchaseToken`（消費型購入ごとに一意）。`UNIQUE (platform, provider_transaction_id)` |
| `provider_order_id` | `TEXT` | NO | NULL | Google `orderId`（`GPA.xxxx` 形式）等。サポート・突合用。Apple は NULL |
| `product_id` | `TEXT` | YES | — | 商品ID（例: `...storage.10gb` / `storage_10gb`） |
| `environment` | `TEXT` | NO | NULL | `'sandbox'` / `'production'` |
| `gb_added` | `INTEGER` | YES | `10` | 追加されたGB数（現仕様は常に10） |
| `price_jpy` | `INTEGER` | YES | — | 購入時の価格（円）。ストアの実売価格ではなく、サーバ側の商品→価格マップ（`product_id` から引く）で記録する。ストア手数料込み表示価格には依存しない。価格改定があっても購入時の値を記録 |
| `purchased_at` | `TIMESTAMPTZ` | YES | `now()` | 購入日時（ストア側の購入確定タイムスタンプ） |
| `expires_at` | `TIMESTAMPTZ` | YES | — | 保管期限。purchased_at の 20 年後を BEFORE INSERT トリガー（`set_storage_purchases_expires_at`）で自動設定する。`GENERATED ALWAYS AS` は PostgreSQL 16 の immutable 制約で使用不可のためトリガー形式を採る（論理的振る舞いは同等） |
| `revoked_at` | `TIMESTAMPTZ` | NO | NULL | 返金・チャージバックで無効化された時刻。NULL = 有効 |
| `created_at` | `TIMESTAMPTZ` | YES | `now()` | レコード作成日時 |

#### 消費型 IAP の検証・冪等性

- **検証（クライアント申告を信用しない）**:
  - Apple: 署名付き transaction（JWS）を x5c 証明書チェーンで Apple Root CA まで検証 → `productId` が対象のストレージ商品であること、`type` = Consumable を確認。必要に応じ App Store Server API で transaction を再取得
  - Google: `purchases.products.get(purchaseToken)` → `purchaseState == 0`（purchased）を確認 → `acknowledge` → `consume`（消費型は消費して再購入可能にする）
- **冪等性**: `UNIQUE (platform, provider_transaction_id)` を主防御とし、記録は `INSERT ... ON CONFLICT (platform, provider_transaction_id) DO NOTHING`。同一購入の二重付与を DB で完全排除する。ストレージ加算は「INSERT が実際に行われた時のみ」実行する

#### インデックス

```sql
CREATE UNIQUE INDEX idx_storage_purchases_provider_txn
    ON storage_purchases (platform, provider_transaction_id);
CREATE INDEX idx_storage_purchases_user_id ON storage_purchases (user_id);
CREATE INDEX idx_storage_purchases_expires_at ON storage_purchases (expires_at);
-- 有効付与量の集計を速める（返金・期限切れを除外）
CREATE INDEX idx_storage_purchases_effective
    ON storage_purchases (user_id)
    WHERE revoked_at IS NULL;
```

#### CHECK 制約

- `gb_added > 0`
- `price_jpy >= 0`
- `platform IN ('apple', 'google')`
- `environment IS NULL OR environment IN ('sandbox', 'production')`

#### 有効追加ストレージの定義

`SUM(gb_added) WHERE revoked_at IS NULL AND expires_at > now()`（§5.3 参照）。

#### immutability（RLS）の方針

Row Level Security（RLS）で UPDATE / DELETE を原則禁止する（アプリ通常ロールは INSERT 権限のみ）。ただし **`revoked_at` カラムのみ、返金処理専用ロールから UPDATE 可**とする例外を設ける。`gb_added` / `price_jpy` 等の他カラムの改竄は引き続き不可。`BEFORE TRUNCATE` 防御・DELETE 禁止は維持し、返金時も行を物理削除しない（監査・社会契約の観点）。

- **代替案の検討**: DELETE による取り消しは監査要件に反するため不採用。返金専用の別テーブル（`storage_revocations`）も検討したが MVP では過剰設計と判断し、`revoked_at` 1列での表現を採用した

#### 外部キー

- `user_id → users(id) ON DELETE RESTRICT`

---

### 3.9 storage_usage

**責務**: カプセル（`capsules`）単位のストレージ使用量スナップショット。画像・音声の実バイト数を保持。`record_attachments` INSERT トリガーにより即時更新される。テキストはカウント対象外。

#### カラム定義

| カラム名 | 型 | NOT NULL | デフォルト | 説明 |
|---------|-----|---------|---------|------|
| `id` | `UUID` | YES | `gen_random_uuid()` | 内部主キー |
| `capsule_id` | `UUID` | YES | — | `capsules.id` への外部キー（UNIQUE: 1カプセル1レコード） |
| `used_bytes` | `BIGINT` | YES | `0` | 画像・音声の合計使用バイト数（テキスト除外） |
| `attachment_count` | `INTEGER` | YES | `0` | 添付ファイル（画像+音声）の総数 |
| `last_calculated_at` | `TIMESTAMPTZ` | YES | `now()` | トリガーが最後に更新した日時 |
| `updated_at` | `TIMESTAMPTZ` | YES | `now()` | レコード更新日時（BEFORE UPDATE トリガーで自動更新。UPSERT 側には `updated_at = NOW()` を記述しない） |

#### インデックス

```sql
CREATE UNIQUE INDEX idx_storage_usage_capsule_id ON storage_usage (capsule_id);
```

#### CHECK 制約

- `used_bytes >= 0`
- `attachment_count >= 0`

#### 外部キー

- `capsule_id → capsules(id) ON DELETE CASCADE`

#### updated_at 更新責務

`updated_at` の更新は `BEFORE UPDATE` トリガー（`trg_storage_usage_updated_at`）に一元化する。`update_storage_usage()` UPSERT 関数の `ON CONFLICT DO UPDATE SET` 側には `updated_at = NOW()` を記述しない（責務の二重化を防ぐ）。

---

### 3.10 unseal_events

**責務**: タイムカプセル開封イベントの記録（1開封 = 1レコード）。開封トリガー（手動/自動）、実行者、実行日時を記録する。開封は不可逆（INSERT only、DELETE/UPDATE 禁止）。

#### カラム定義

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|---------|------|
| `id` | `UUID` | NOT NULL | `gen_random_uuid()` | 主キー 内部ID |
| `capsule_id` | `UUID` | NOT NULL | — | 外部キー: capsules(id) ON DELETE CASCADE |
| `trigger_type` | `VARCHAR(20)` | NOT NULL | — | `'manual'`（任意開封）または `'scheduled'`（開封日自動開封） |
| `executed_by` | `UUID` | NULL | — | 外部キー: users(id) ON DELETE SET NULL。自動開封時は NULL |
| `executed_at` | `TIMESTAMPTZ` | NOT NULL | `CURRENT_TIMESTAMP` | 開封実行日時（配信完了時刻ではない） |
| `notification_sent_at` | `TIMESTAMPTZ` | NULL | — | 全配信先への通知送信完了日時。NULL = 送信保留中 |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `CURRENT_TIMESTAMP` | レコード作成日時（監査用） |

#### インデックス

```sql
-- 開封履歴一覧
CREATE INDEX idx_unseal_events_capsule_id ON unseal_events(capsule_id);
-- 未送信通知のバッチ処理
CREATE INDEX idx_unseal_events_notification_pending
    ON unseal_events(capsule_id, notification_sent_at)
    WHERE notification_sent_at IS NULL;
```

#### CHECK 制約

- `trigger_type IN ('manual', 'scheduled')`

#### 外部キー

- `capsule_id → capsules(id) ON DELETE CASCADE`
- `executed_by → users(id) ON DELETE SET NULL`

---

### 3.11 email_deliveries

**責務**: メール配信ログ（開封通知・記録配信・招待・バウンス警告・開封日変更通知・トライアル終了リマインダーの6タイプ）。リトライ管理（最大3回・24時間以内）と visibility フィルタ証跡の保持を担う。

#### カラム定義

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|---------|------|
| `id` | `UUID` | NOT NULL | `gen_random_uuid()` | 主キー 内部ID |
| `capsule_id` | `UUID` | NOT NULL | — | 外部キー: capsules(id) ON DELETE CASCADE |
| `record_id` | `UUID` | NULL | — | 外部キー: records(id) ON DELETE RESTRICT。記録配信時に入力。開封通知は NULL |
| `delivery_address_id` | `UUID` | NOT NULL | — | 外部キー: delivery_addresses(id) ON DELETE RESTRICT |
| `unseal_event_id` | `UUID` | NULL 許容（email_type 条件付き） | — | 外部キー: unseal_events(id) ON DELETE RESTRICT。`unseal_notice` / `record_delivery` 時のみ必須、`invite` / `bounce_warning` / `open_at_change` / `trial_reminder` 時は NULL（CHECK 制約で整合性強制。`trial_reminder` は開封イベントと無関係のため不要。2026-07-03 追記） |
| `email_type` | `VARCHAR(50)` | NOT NULL | — | `'unseal_notice'` / `'record_delivery'` / `'invite'` / `'bounce_warning'` / `'open_at_change'`（開封日変更通知） / `'trial_reminder'`（トライアル終了3日前/1日前リマインダー。product-spec.md §6.5。2026-07-03 追記） |
| `resend_message_id` | `VARCHAR(255)` | NULL | — | Resend API からの返却 message_id |
| `status` | `VARCHAR(20)` | NOT NULL | `'pending'` | `'pending'` / `'sent'` / `'delivered'` / `'bounced'` / `'failed'` / `'skipped'` |
| `attempt_count` | `SMALLINT` | NOT NULL | `1` | 送信試行回数（1-3） |
| `last_attempted_at` | `TIMESTAMPTZ` | NULL | — | 最後の送信試行日時 |
| `error_message` | `TEXT` | NULL | — | バウンス理由・エラーメッセージ詳細 |
| `skipped_reason` | `VARCHAR(100)` | NULL | — | status='skipped' 時の理由。例: "no_matching_tag" |
| `created_at` | `TIMESTAMPTZ` | NOT NULL | `CURRENT_TIMESTAMP` | レコード作成日時 |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL | `CURRENT_TIMESTAMP` | 最終更新日時（リトライ試行時に更新） |

#### インデックス

```sql
CREATE INDEX idx_email_deliveries_capsule_id ON email_deliveries(capsule_id);
-- 開封イベント × 配信先の複合検索
CREATE INDEX idx_email_deliveries_unseal_event_delivery
    ON email_deliveries(unseal_event_id, delivery_address_id);
-- リトライ対象検索（失敗・3回未満・24h以上経過）
CREATE INDEX idx_email_deliveries_retry_candidates
    ON email_deliveries(status, attempt_count, last_attempted_at)
    WHERE status = 'failed' AND attempt_count < 3;
-- 配信先別の配信状況（バウンス警告用）
CREATE INDEX idx_email_deliveries_delivery_address
    ON email_deliveries(delivery_address_id, status);
-- 記録配信ログの検索
CREATE INDEX idx_email_deliveries_record_id
    ON email_deliveries(record_id)
    WHERE record_id IS NOT NULL;
```

#### CHECK 制約

- `email_type IN ('unseal_notice', 'record_delivery', 'invite', 'bounce_warning', 'open_at_change', 'trial_reminder')`（2026-07-03 追記: `trial_reminder` を追加）
- `status IN ('pending', 'sent', 'delivered', 'bounced', 'failed', 'skipped')`
- `attempt_count BETWEEN 1 AND 3`
- `chk_email_deliveries_unseal_event_consistency`: `email_type` と `unseal_event_id` の整合性を強制する。`unseal_notice` / `record_delivery` は開封イベント由来のため `unseal_event_id IS NOT NULL` を要求し、`invite` / `bounce_warning` / `open_at_change` / `trial_reminder` は開封イベントと無関係のため `unseal_event_id IS NULL` を要求する（`trial_reminder` は `subscriptions.trial_end` 起点のバッチ由来であり `unseal_events` を必要としない。2026-07-03 追記）。これにより `unseal_event_id` を NULL 許容にしながら、必要な型のメールについては必ず紐付けが保証される

#### 外部キー

- `capsule_id → capsules(id) ON DELETE CASCADE`
- `record_id → records(id) ON DELETE RESTRICT`（records は INSERT only で物理削除不可。将来 records を削除可能にした場合の配信ログ自動消失を防ぐため CASCADE を使用しない）
- `delivery_address_id → delivery_addresses(id) ON DELETE RESTRICT`（監査担保のため削除不可）
- `unseal_event_id → unseal_events(id) ON DELETE RESTRICT`（不可逆性）

---

### 3.12 export_jobs（2026-07-03 追記）

**責務**: 非同期データエクスポート（api-spec.md §6.4 `POST /capsules/{id}/export` → `202` 受理、§6.5 `GET /capsules/{id}/export/{jobId}` でのポーリング）のジョブ状態を永続化する。サーバー/ワーカーの再起動をまたいでもジョブの受理・進行状況・生成物の所在・失敗理由が失われないことを担保する（着手前論点 §12-9 の決定）。

#### カラム定義

| カラム名 | 型 | NULL | デフォルト | 説明 |
|---------|-----|------|---------|------|
| `id` | `UUID` | NOT NULL | `gen_random_uuid()` | 内部主キー。api-spec.md §6.4/§6.5 の `export_job_id` に対応 |
| `capsule_id` | `UUID` | NOT NULL | — | エクスポート対象カプセル（`capsules.id` への FK） |
| `requested_by` | `UUID` | NOT NULL | — | 要求者（`users.id` への FK）。§6.5 の「要求者本人のみ閲覧可」認可はこのカラムで判定する |
| `status` | `TEXT` | NOT NULL | `'queued'` | ジョブ状態。`'queued'` / `'processing'` / `'completed'` / `'failed'`（api-spec.md §6.5 の状態語彙と一致） |
| `scope` | `TEXT` | NOT NULL | — | エクスポート範囲。`'sealed_self_only'`（封印中・自分の記録のみ）/ `'unsealed_all'`（開封後・全記録）。リクエスト受理時点のカプセル状態から確定し、生成完了まで不変（api-spec.md §6.4） |
| `formats` | `TEXT[]` | NOT NULL | — | 要求された生成形式の配列。各要素は `'pdf'` / `'json'` / `'markdown'`（api-spec.md §6.4 の `formats` リクエストボディをそのまま保持） |
| `object_keys` | `JSONB` | NULL | `NULL` | 完成物の S3 オブジェクトキーを `{"pdf": "...", "json": "...", "markdown": "..."}` 形式で保持。`status='completed'` になった時点で `formats` の全要素分を設定する |
| `error_message` | `TEXT` | NULL | `NULL` | `status='failed'` 時のエラー詳細 |
| `requested_at` | `TIMESTAMPTZ` | NOT NULL | `now()` | ジョブ受理日時（`202` レスポンスの `requested_at` に対応） |
| `completed_at` | `TIMESTAMPTZ` | NULL | `NULL` | 生成完了日時（`status IN ('completed','failed')` になった時刻） |
| `expires_at` | `TIMESTAMPTZ` | NULL | `NULL` | 生成物ダウンロード URL（S3 presigned GET）の失効日時。`status='completed'` になった時点で設定する |

#### 1 ジョブ = 複数フォーマットという設計（`format` 単一列を採らなかった根拠）

api-spec.md §6.4 のリクエストボディ `formats` は配列であり、1 回の `POST` で PDF/JSON/Markdown を同時に生成し、`export_job_id` は 1 個だけ発行される（§6.5 のレスポンスも `formats` 配列 + `download_urls` マップで返る）。そのため本テーブルは「1 行 = 1 ジョブ（複数フォーマットをまとめて内包）」を採用し、`format TEXT` の単一値カラムではなく `formats TEXT[]` + `object_keys JSONB` で複数フォーマット分の状態を 1 行に持たせる。フォーマットごとに行を分けると `export_job_id` と行が 1:N になり、§6.5 の「1 jobId → 1 レスポンス（複数 `download_urls`）」という API 形状と食い違うため採用しない。

#### `status` に `'expired'` を含めない根拠

api-spec.md §6.5 が定義する状態語彙は `queued` / `processing` / `completed` / `failed` の 4 種のみであり、ダウンロード URL の失効は `status` ではなく `expires_at`（本テーブル）と S3 presigned GET 自体の失効で表現される（`status='completed'` のまま `expires_at` を過ぎる）。ジョブそのものが「失効」して別状態に遷移する仕様は api-spec.md に存在しないため、`status` CHECK には `'expired'` を含めない。

#### インデックス

```sql
-- カプセル単位のジョブ一覧・監査
CREATE INDEX idx_export_jobs_capsule_id ON export_jobs (capsule_id);

-- 要求者本人認可チェック（GET /capsules/{id}/export/{jobId}）・自分のジョブ一覧
CREATE INDEX idx_export_jobs_requested_by ON export_jobs (requested_by);

-- ワーカーのキュー取り出し（未完了ジョブのみ）
CREATE INDEX idx_export_jobs_status_pending
    ON export_jobs (status, requested_at)
    WHERE status IN ('queued', 'processing');

-- 生成物の有効期限切れクリーンアップバッチ
CREATE INDEX idx_export_jobs_expires_at
    ON export_jobs (expires_at)
    WHERE expires_at IS NOT NULL;
```

#### CHECK 制約

- `status IN ('queued', 'processing', 'completed', 'failed')`
- `scope IN ('sealed_self_only', 'unsealed_all')`
- `chk_export_jobs_formats_valid`: `formats` は空でなく、要素は `pdf`/`json`/`markdown` のみ:
  ```sql
  array_length(formats, 1) > 0
  AND formats <@ ARRAY['pdf', 'json', 'markdown']::TEXT[]
  ```
- `chk_export_jobs_completion_consistency`: 完了時は成果物・完了日時が揃っていること:
  ```sql
  (status = 'completed' AND object_keys IS NOT NULL AND completed_at IS NOT NULL)
  OR (status != 'completed')
  ```
- `chk_export_jobs_failure_consistency`: 失敗時はエラーメッセージ・完了日時が揃っていること:
  ```sql
  (status = 'failed' AND error_message IS NOT NULL AND completed_at IS NOT NULL)
  OR (status != 'failed')
  ```

#### 外部キー

- `capsule_id → capsules(id) ON DELETE CASCADE`（`delivery_addresses` / `storage_usage` / `unseal_events` / `email_deliveries` と同じ「カプセル付随ログ」方針を踏襲。§4.10）
- `requested_by → users(id) ON DELETE RESTRICT`（`subscriptions.user_id` / `storage_purchases.user_id` と同じ方針。users は物理削除禁止のため実質発火しない）

---

## 4. 設計判断の根拠

### 4.1 主キー方針: 内部UUID

全テーブルで `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` を採用する。

**根拠**:
- 外部に公開しないことで、内部IDの推測によるアクセス攻撃を防ぐ
- Firebase UID やストア購読識別子などの外部サービスIDは別カラムで管理し、外部キーとしては使用しない
- UUIDによりIDの衝突リスクがなく、分散システムへの将来的な移行が容易

### 4.2 状態管理: 冗長カラムの例外（capsules.unsealed_at）

封印状態を `unsealed_at TIMESTAMPTZ NULL` で管理する（NULL=封印中、値あり=開封済み）。

**根拠**:
- 開封日時という有用な情報を保持しつつ、`NULL` による封印中/開封済みの二値状態を一つのカラムで表現できる
- `is_unsealed BOOLEAN` + `unsealed_at TIMESTAMPTZ` の2カラムにすると整合性を別途管理する必要がある
- 開封トリガー種別（手動/自動）は `unseal_trigger` カラムに分離し、責務を明確化する

### 4.3 削除方針: users 物理削除禁止 / records 永続保持 / INSERT only テーブルの TRUNCATE 防御

**users 物理削除禁止**:
- 「削除された参加者の記録は、家族の財産として保持される」という社会契約宣言に基づく
- `is_deleted = TRUE` + `deleted_at` による論理削除のみ許可
- 退会後5年を目安に PII（display_name / email / firebase_uid）を NULL またはプレースホルダ値で**匿名化**（`anonymize_scheduled_at` で匿名化実施予定日時を管理）。IAP 購読識別子（`original_transaction_id` 等）は `subscriptions` 側にあり PII ではないため、匿名化の即時対象ではない
- 個人情報保護法・GDPR 対応は「匿名化」によって本人特定性を排除することで実質的に満たす

**records 永続保持**（社会契約宣言「家族の財産」履行）:
- records は物理削除禁止。退会後も記録は永続保持する
- users の PII 匿名化によって退会者本人との紐付けは切れるため、プライバシー要件と両立できる
- INSERT only（`BEFORE UPDATE OR DELETE` トリガーで即時エラー）を維持する

**INSERT only テーブルへの TRUNCATE 防御**:
- `BEFORE UPDATE OR DELETE` トリガーだけでは `TRUNCATE` 経路での全消去を防げない
- 以下のテーブルに `BEFORE TRUNCATE` トリガーも追加してテーブル全消失を防ぐ:
  - `records` / `record_attachments` / `unseal_events` / `storage_purchases`
- `record_attachments` にも `prevent_records_mutation` 相当の INSERT only トリガーを張り、DB レベルで削除・更新を禁止する
- `storage_purchases` は上記 TRUNCATE 防御を維持しつつ、`revoked_at` カラムのみ返金処理専用ロールから UPDATE 可とする例外を設ける（§3.8 参照。消費型 IAP は返金が現実に発生するため、完全 immutable の前提を見直した）

**storage_purchases.expires_at の実装**:
- 当初 `GENERATED ALWAYS AS (purchased_at + INTERVAL '20 years') STORED` として定義することを検討したが、PostgreSQL 16 の `GENERATED ALWAYS AS` は immutable 関数のみ使用可能という制約に抵触する
- `TIMESTAMPTZ + INTERVAL` の演算は PostgreSQL 内部で stable/volatile 扱いとなるため、BEFORE INSERT トリガー `set_storage_purchases_expires_at()` で代替する
- 外部から見た振る舞いは同等（INSERT 時に `purchased_at + 20年` が自動設定される）

### 4.4 1週間ウィンドウ: window_ends_at の事前計算

**計算式**:
```
投稿日翌日0時JST起算で7日間
window_ends_at = timezone('Asia/Tokyo',
                     date_trunc('day', timezone('Asia/Tokyo', posted_at)) + INTERVAL '8 days'
                 )
```

> PostgreSQL 16 の `GENERATED ALWAYS AS` は immutable 関数のみ使用可能という制約があるため、`AT TIME ZONE` 演算子ではなく `timezone(text, timestamptz)` 関数形式（immutable）を採用する。

**根拠**:
- `window_ends_at > NOW()` で現在ウィンドウ中かを O(1) で判定可能
- 毎回 `posted_at` から計算するより、インデックスを活用した高速な範囲検索ができる
- `GENERATED ALWAYS AS` 生成列として定義することでトリガーが DROP / DISABLE されても整合性が崩れない。アプリ層の計算ミスも入り込まない
- `timezone(text, timestamptz)` は PostgreSQL 組み込みの immutable 関数であり、`GENERATED ALWAYS AS` 列内で安全に使用できる

### 4.5 visibility と delivery_addresses.tag の照合

- `records.visibility = 'all'` → 全配信先に配信
- `records.visibility = 'parents_only'` → `delivery_addresses.tag = 'parents_only'` のメアドにのみ配信
- 全配信先が `tag = 'all'` かつ `parents_only` 記録のみの場合、配信が一件もない
- スキップされた配信も `email_deliveries` に `status = 'skipped', skipped_reason = 'no_matching_tag'` として記録し、配信意志の証跡を保持する

### 4.5.1 email_deliveries.unseal_event_id の整合性制約

`email_deliveries` には開封イベントに由来するメール（`unseal_notice` / `record_delivery`）と、開封イベントとは独立して送信されるメール（`invite` / `bounce_warning` / `open_at_change` / `trial_reminder`）の両方が混在する。`unseal_event_id` を NULL 許容に変更し、`email_type` との整合性を `chk_email_deliveries_unseal_event_consistency` CHECK 制約で強制する方針を採用した。これにより：

- `unseal_notice` / `record_delivery` → `unseal_event_id IS NOT NULL`（開封イベント必須）
- `invite` / `bounce_warning` / `open_at_change` / `trial_reminder` → `unseal_event_id IS NULL`（開封と無関係。`trial_reminder` は `subscriptions.trial_end` 起点のトライアル終了バッチ由来。product-spec.md §6.5。2026-07-03 追記）

という二律背反の制約を DB 層で確実に保証できる。外部キー `fk_email_deliveries_unseal_event` は `ON DELETE RESTRICT` のままで問題ない（`unseal_events` は INSERT only のため実際には発火しない）。

この「NULL 許容カラムを CHECK で整合強制する」流儀は、`subscriptions` のプラットフォーム識別子整合制約（§3.7）でも踏襲している。

### 4.6 ストレージ集計: capsule 単位・即時更新

`storage_usage` テーブルは `capsule_id` を単位とし、`record_attachments` INSERT トリガーで即時 UPSERT 更新する。

**capsule_id を採用した根拠**:
- 複数参加者がいるカプセルで誰のストレージを消費するか曖昧になる問題を回避（user_id 採用の場合の欠点）
- 削除された参加者の書いた記録のバイト数の帰属問題を解消
- 「カプセルのオーナーがそのカプセルのストレージ上限を管理する」という課金モデルと整合

**即時更新を採用した根拠**:
- ストレージ残量チェック（上限到達防止）をリクエスト単位で実施可能
- バッチ集計では最新値との乖離が生じ、上限超過を許してしまうリスクがある

### 4.7 プラン情報の同期フロー（ストア通知 → subscriptions → users キャッシュ）

`subscriptions.plan_type` + `subscriptions.status` が真実の源——ただし前述の通り、その真実は Apple / Google ストア側にある。当方は S2S 通知＋検証 API で取得した状態を保存するだけであり、「通知は"変化があった"合図に過ぎず、状態は検証 API を叩いて取り直す」という発想を取る（特に Google RTDN は購読状態そのものを通知本文に含まないため必須）。`users.current_plan` は読み取り速度を確保するための非正規化キャッシュ。

#### Apple: App Store Server Notifications V2

1. Apple → `POST /webhooks/apple/notifications`（本文 = `signedPayload`、JWS）
2. **署名検証**: x5c 証明書チェーンを Apple Root CA まで検証。失敗は 400 で拒否
3. デコード → `notificationType` + `subtype` + `data.signedTransactionInfo` + `data.signedRenewalInfo`。`environment` を取得
4. `original_transaction_id` で `subscriptions` を逆引き（無ければ `appAccountToken = users.id` で user を特定して新規行を作成）
5. §3.7 のマッピング表で status を導出し、`current_period_end` / `auto_renew` / `latest_notification_type` / `latest_notification_at` 等を更新
6. **同一トランザクション内で `users.current_plan` を再計算・更新**（エンタイトルメント無なら `'free'`）

#### Google: Real-time Developer Notifications（RTDN）

1. Pub/Sub → `POST /webhooks/google/rtdn`（push、base64 エンコードされた `message.data`）
2. デコード → `subscriptionNotification`（`purchaseToken` / `subscriptionId` / `notificationType`）または `voidedPurchaseNotification` / `oneTimeProductNotification`
3. **通知本文だけで状態を決めない。** `purchases.subscriptionsv2.get(purchaseToken)`（サブスク）/ `purchases.products.get`（消費型）で権威状態を取得する
4. `purchase_token` で逆引き。ローテーション時は `linkedPurchaseToken` 連鎖・`obfuscatedExternalAccountId = users.id` で同一 user 行を特定し、`purchase_token` を最新値に UPDATE する
5. status 導出以降は Apple と同じ（同一トランザクションで `users.current_plan` を更新）

#### 冪等性・順序保証

- **サブスク**: キーは `original_transaction_id` / `purchase_token`。UPSERT で冪等にする。加えて **`latest_notification_at`（Apple `signedDate` / Google 取得状態の `eventTime`）による単調ガード**を設ける: 受信イベントが保存済みより古ければ破棄する（順不同・再送によって古い状態に巻き戻さないため）
- **消費型**: `UNIQUE (platform, provider_transaction_id)` + `ON CONFLICT DO NOTHING` が冪等の主防御（重複付与ゼロ）
- 専用の `processed_notifications` テーブルは MVP では作らない（Apple `notificationUUID` / Pub/Sub `messageId` による厳密重複排除も可能だが、「冪等 UPSERT ＋ 単調ガード ＋ UNIQUE」で十分と判断し、過剰設計を回避する）
- 不整合が発生した場合は `subscriptions` を正として扱い、定期バッチで `users.current_plan` キャッシュを修復する

#### リストア購入・識別子競合

別端末での購入復元は同じ購読識別子で通知が来るため、`UNIQUE(user_id)` と識別子 UNIQUE の下で冪等 UPSERT すれば足りる。ただし別ユーザーが同一識別子を主張した場合（family 共有・中古端末等）は、識別子 UNIQUE 側を正として既存ユーザー行を維持し（新ユーザーへの付け替えはしない）、競合としてログに残しサポート対応に回す。

### 4.8 インデックス方針

- **部分インデックス（Partial Index）を積極採用**: `WHERE is_deleted = FALSE` / `WHERE unsealed_at IS NULL` / `WHERE revoked_at IS NULL` など、実際のクエリで必要な行のみをインデックス対象にすることでインデックスサイズと更新コストを削減
- **複合インデックスの順序**: 絞り込み効果の高いカラムを先頭に（例: `(capsule_id, window_ends_at)`, `(capsule_id, status)`）
- **UNIQUE制約はインデックスとして機能**: Firebase UID・email・ストア購読識別子などの高頻度ルックアップカラムは UNIQUE 制約で二重の恩恵を得る
- **プラットフォーム別 部分UNIQUE**: 新識別子カラム（`original_transaction_id` / `purchase_token` / `(platform, provider_transaction_id)`）は単一グローバル UNIQUE にせず、`WHERE ... IS NOT NULL` の部分 UNIQUE にする（無料行の NULL 衝突・プラットフォーム混載を避けるため）
- **テキスト/メールの大文字小文字統一**: `delivery_addresses` と `capsule_members` の email 系列に `LOWER()` 関数インデックスを使用。email は LOWER() で正規化し UNIQUE INDEX を張ることで、大文字小文字の違いによる重複登録・重複配信を防ぐ

### 4.9 タイムゾーン処理（JST基準）

- **DB保存値は常に UTC（TIMESTAMPTZ）**
- **1週間ウィンドウの計算は JST 基準**（投稿日翌日0時JST起算）
- **月次記録カウントも JST 基準**（月初〜月末JSTの範囲）
- **クライアントへの返却時に JST 変換**（アプリ層で `AT TIME ZONE 'Asia/Tokyo'` 変換またはフロントエンドで処理）
- `users.timezone` に各ユーザーのタイムゾーンを保持することで、将来の多言語対応・タイムゾーン切り替えに対応可能

### 4.10 外部キー方針（RESTRICT / SET NULL / CASCADE の使い分け）

| 方針 | 適用ケース | 具体例 |
|------|-----------|--------|
| `ON DELETE RESTRICT` | 参照先の削除が業務上不正となる場合。参照元が業務記録として独立した意味を持つ | `records.author_id → users`, `records.capsule_id → capsules`, `subscriptions.user_id → users`, `storage_purchases.user_id → users`, `email_deliveries.delivery_address_id → delivery_addresses`（監査担保）, `email_deliveries.record_id → records`（将来の records 削除許可時の配信ログ消失防止）, `export_jobs.requested_by → users`（2026-07-03 追記） |
| `ON DELETE SET NULL` | 参照先が削除されても参照元レコードの存在価値が失われない場合 | `unseal_events.executed_by → users(id) ON DELETE SET NULL`（監査要件 + users 物理削除禁止のため users.id を採用。自動開封時は NULL）, `delivery_addresses.added_by → users` |
| `ON DELETE CASCADE` | 親レコード削除時に子レコードも連動削除することが業務上自然な場合 | `delivery_addresses.capsule_id → capsules`（カプセル削除時に配信先も削除）, `storage_usage.capsule_id → capsules`, `unseal_events.capsule_id → capsules`, `email_deliveries.capsule_id → capsules`, `export_jobs.capsule_id → capsules`（2026-07-03 追記） |

---

## 5. 主要クエリパターン

### 5.1 封印モードアーカイブ（他参加者の1週間以内の記録を取得）

```sql
-- 自分以外の参加者の、まだウィンドウ内の記録を取得（全員向け）
SELECT r.id, r.author_id, r.body, r.visibility, r.posted_at, r.window_ends_at
FROM records r
JOIN capsule_members cm ON cm.capsule_id = r.capsule_id
    AND cm.user_id = :viewer_user_id
    AND cm.status = 'active'
WHERE r.capsule_id = :capsule_id
  AND r.author_id != :viewer_user_id
  AND r.window_ends_at > NOW()
ORDER BY r.posted_at DESC;
```

### 5.2 開封日バッチ（開封日到来の未開封カプセルを検出）

```sql
-- 開封日が今日以前でまだ開封されていないカプセルを取得
SELECT c.id, c.name, c.open_at
FROM capsules c
WHERE c.open_at <= NOW()
  AND c.unsealed_at IS NULL
ORDER BY c.open_at ASC;
```

### 5.3 ストレージ残量計算（カプセルオーナーの残ストレージ）

```sql
-- カプセルオーナーの総ストレージ上限 = 基本5GB + 有効な買い切り追加分
WITH owner_storage AS (
    SELECT
        5 * 1024 * 1024 * 1024 AS base_bytes,
        COALESCE(SUM(sp.gb_added) * 1024 * 1024 * 1024, 0) AS purchased_bytes
    FROM storage_purchases sp
    WHERE sp.user_id = :owner_user_id
      AND sp.revoked_at IS NULL
      AND sp.expires_at > NOW()
),
capsule_usage AS (
    SELECT COALESCE(SUM(su.used_bytes), 0) AS used_bytes
    FROM storage_usage su
    JOIN capsules c ON c.id = su.capsule_id
    WHERE c.created_by = :owner_user_id
)
SELECT
    os.base_bytes + os.purchased_bytes AS total_limit_bytes,
    cu.used_bytes,
    os.base_bytes + os.purchased_bytes - cu.used_bytes AS remaining_bytes
FROM owner_storage os, capsule_usage cu;
```

> `revoked_at IS NULL` 条件により、返金・チャージバックされた購入は残量計算から除外される（§3.8）。

### 5.4 月次記録数カウント（JST月単位）

```sql
-- 当月の記録件数（無料5件/有料200件の上限判定用）
SELECT COUNT(*) AS monthly_record_count
FROM records
WHERE author_id = :user_id
  AND posted_at >= date_trunc('month', NOW() AT TIME ZONE 'Asia/Tokyo') AT TIME ZONE 'Asia/Tokyo'
  AND posted_at <  date_trunc('month', NOW() AT TIME ZONE 'Asia/Tokyo') AT TIME ZONE 'Asia/Tokyo'
                   + INTERVAL '1 month';
```

### 5.5 リトライ対象メール配信の検出（バッチジョブ）

```sql
-- 失敗した配信のうち、試行回数3回未満のものを取得（5分以上経過を条件にバッチで実行）
SELECT ed.id, ed.capsule_id, ed.record_id, ed.delivery_address_id,
       ed.email_type, ed.attempt_count, da.email
FROM email_deliveries ed
JOIN delivery_addresses da ON da.id = ed.delivery_address_id
WHERE ed.status = 'failed'
  AND ed.attempt_count < 3
  AND ed.last_attempted_at < NOW() - INTERVAL '5 minutes'
ORDER BY ed.last_attempted_at ASC;
```

---

## 6. 未解決事項・Phase 2 への申し送り

### 6.1 AI機能追加時の records 拡張余地

MVP では `records.body` はテキストのみ。将来のAI機能（感情分析・自動タグ付け・要約生成）追加時には以下の拡張を検討する:
- `records.ai_summary TEXT` — AI生成要約
- `records.sentiment_score FLOAT` — 感情分析スコア
- `records.tags TEXT[]` — 自動タグ配列（PostgreSQL の配列型を活用）

テーブル分割（`record_ai_metadata`）の方が ALTER TABLE なしで追加可能なため、Phase 2 では別テーブルを推奨。

### 6.2 製本オプション

開封後に全記録をPDF製本する機能。追加テーブル案:
- `print_orders` — 製本注文管理（capsule_id, status, shipping_address_id など）
- `print_order_items` — 含める記録の選定

`delivery_addresses.tag` の `'parents_only'` フィルタと同様に、製本対象記録の可視性制御が必要。

### 6.3 動画記録

MVP では `record_attachments.attachment_type` に `'video'` は含まない。Phase 2 追加時には:
- CHECK 制約の変更: `attachment_type IN ('image', 'audio', 'video')`
- `duration_seconds` は動画にも適用可能（既存カラムを再利用）
- S3 オブジェクトキー命名規約の拡張（`mp4` 等）

### 6.4 認証プロバイダ移行

現在は Firebase Auth のみ対応（`users.firebase_uid`）。将来、他の Auth プロバイダへの移行が必要になった場合:
- `users` に `auth_provider TEXT NOT NULL DEFAULT 'firebase'` カラムを追加
- `auth_uid TEXT NOT NULL` に統一し、`firebase_uid` カラムを廃止
- マイグレーション期間中は両カラムを並行保持する計画が必要

### 6.5 terms_consents 履歴テーブル

現在は `users.terms_agreed_at` と `users.terms_version` の2カラムで同意を管理。規約バージョンの変更履歴が必要になった場合は `terms_consents` 履歴テーブルを追加する（MVPでは `users` の2カラムで十分）。

### 6.6 配信先グループ化・配信優先度

`delivery_addresses` は現在フラットなリスト構造。Phase 2 で想定される拡張:
- `delivery_group_id` を追加してグループ化
- `priority INTEGER` で配信順序を制御
- `delivery_logs` テーブルによる詳細な配信成功/失敗履歴の永続化

### 6.7 app_role の冪等作成

初期スキーマ定義の冒頭（拡張機能セクション直後）に以下の DO ブロックを追加し、`app_role` を冪等的に作成すること。これによりクリーン DB へのスキーマ適用時に `ERROR: role "app_role" does not exist` で停止する問題を回避できる:

```sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_role') THEN
        CREATE ROLE app_role NOLOGIN;
    END IF;
END
$$;
```

### 6.8 退会後の完全消去要件が厳格化された場合の再設計

現在の退会後ポリシーは「users PII 匿名化 / records 永続保持」で確定。個人情報保護法・GDPR 対応は匿名化によって本人特定性を排除することで実質的に満たす。

完全消去要件が将来法的に厳格化された場合は、**records 個別削除を許可する別経路を Phase 2 で再設計**する（`prevent_records_mutation` トリガーに session 変数で管理するパージモード例外を組み込む等）。

### 6.9 unseal_events INSERT 時の capsules.unsealed_at 自動同期

現状、`unseal_events` 挿入時の `capsules.unsealed_at` 更新はアプリ層責任。AFTER INSERT トリガーで自動同期させることで整合性を DB 層で担保する設計を **Phase 2 で検討**する。

### 6.10 開封済みカプセルへの新規参加禁止

`capsule_members` INSERT 時に `capsules.unsealed_at IS NULL` をチェックするトリガーを追加し、開封済みカプセルへの参加禁止を DB レベルで強制することを **Phase 2 で検討**する（MVP はアプリ層チェックのみ）。

### 6.11 参加者・配信先の上限を DDL レベルで強制

参加者2人・配信先5個の上限は現状アプリ層チェックのみ。課金プラン変更時の整合性を高めるため、`capsule_members` / `delivery_addresses` の INSERT トリガーで件数 CHECK を行う DDL レベルの二重防御を **Phase 2 で検討**する。

### 6.12 invite/bounce_warning/open_at_change/trial_reminder 系メールの独立運用

`email_deliveries` テーブルの `invite` / `bounce_warning` / `open_at_change` / `trial_reminder`（2026-07-03 追記）系のメールは開封イベントと独立して送信される（`unseal_event_id = NULL`）。これらはカプセルの封印状態に関わらず任意のタイミングで発生し得るため、開封イベントへの強制紐付けは設計上不正確であった。CHECK 制約（`chk_email_deliveries_unseal_event_consistency`）によってこの分離が DB レベルで保証される。アプリ層でこれらのメールを INSERT する際は `unseal_event_id` を明示的に NULL とすること。`trial_reminder` は `subscriptions.trial_end` の3日前・1日前に発火するトライアル終了バッチ由来（product-spec.md §6.5）で、`capsule_id` はユーザーが所属するカプセルのいずれか（または通知設計次第で複数行）に紐付ける想定。具体的な紐付けルールの確定は実装スライスで行う。

### 6.13 Google purchaseToken ローテーション追跡

アップグレード/再購読で古いトークンの行を UPDATE し損ねると二重行・エンタイトルメント誤りが発生し得る。`linkedPurchaseToken` 連鎖の追跡実装レビューを必須項目とする（§4.7）。

### 6.14 processed_notifications テーブルの要否再検討

MVP では「冪等 UPSERT ＋ `latest_notification_at` 単調ガード ＋ UNIQUE 制約」で通知の冪等性を担保し、専用の重複排除テーブルは作らない方針とした（§4.7）。運用上の重複・順序逆転が実際に問題化した場合は、Apple `notificationUUID` / Pub/Sub `messageId` による厳密重複排除テーブルの追加を Phase 2 で再検討する。

---

## 修正履歴

| バージョン | 日付 | 内容 |
|---|---|---|
| v1.0 | 2026-07-02 | IAP反映版。課金モデルを Stripe から Apple/Google IAP に全面再設計（`users.stripe_customer_id` 削除、`subscriptions`/`storage_purchases` のプラットフォーム識別子化、プラン同期フローの Apple ASSN V2 + Google RTDN 2系統化、消費型ストレージ購入の返金対応 `revoked_at` 新設）。billing 以外の8テーブルは既存設計を踏襲 |
| v1.1 | 2026-07-03 | 仕様の穴3件を追記。(1) `capsule_members` に `invite_token_hash` / `invite_token_expires_at` を追加（招待トークンのハッシュ保存方式。§3.3・§1 ER図）。(2) `email_deliveries.email_type` CHECK に `'trial_reminder'` を追加（トライアル終了3日前/1日前通知。§3.11・§4.5.1・§6.12）。DDL/マイグレーションは未反映（仕様書のみの追記。実装は別スライス） |
| v1.2 | 2026-07-03 | 着手前論点（PHASE1-BACKEND-KICKOFF-PROMPT.md §12）のエンジニア決定を反映。`export_jobs` テーブルを12テーブル目として新設（非同期エクスポートジョブ〔api-spec.md §6.4/§6.5〕の状態・要求者・生成物 S3 キー・失敗理由・有効期限を永続化。§1 ER図・§2 テーブル一覧・§3.12・§4.10）。DDL/マイグレーションは未反映（仕様書のみの追記。実装は B9 スライスで行う） |
