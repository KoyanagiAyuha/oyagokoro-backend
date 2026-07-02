# おやごころ Phase 1 バックエンド開発キックオフ プロンプト

> このファイルは Phase 1 バックエンド開発専用の新セッション開始時に最初に読み込ませるプロンプトです。
> Phase 0 完了時点（2026-05-27）で部長が作成。
> フロントエンド開発は別セッションで進行（PHASE1-FRONTEND-KICKOFF-PROMPT.md・後日作成）。

---

## 0. このセッションのゴール

**Phase 1 バックエンド: 課長計画書のスライス順序（B-Slice-1 〜 B-Slice-9）に従って API を段階実装。**

各スライスごとに「動く API 群」を pytest + curl で疎通確認しながら積み上げる。フロントエンドは別セッションで並行進行（実 API を順次叩く想定）。

---

## 1. プロジェクト概要（要約）

- **名称**: おやごころ（lydear エコシステム第1弾）
- **配信 URL**: https://oyagokoro.lydear.com
- **コンセプト**: 家族の20年タイムカプセル（思想を強制せず、設定で柔軟）

詳細: [specs/oyagokoro-spec.md](specs/oyagokoro-spec.md) v0.7

---

## 2. このセッションが触るリポジトリ

`/Users/ayuhakoyanagi/Desktop/workspace/oyagokoro-backend/`

独立 git リポジトリ。Phase 0 完了時点で `074ada9` 初回コミット済み。

**触らないリポジトリ**:
- `oyagokoro-frontend/` — フロントエンド側セッションの担当範囲
- `oyagokoro/` — 仕様書・設計書ドキュメントの共有領域（Phase 1 で更新は基本なし）

---

## 3. Phase 0 で完成済みのもの（再確認）

### 技術スタック
- FastAPI + uv 管理（Python 3.12）
- SQLAlchemy 2.x async + Alembic
- PostgreSQL 16 on Docker Compose（pgcrypto 拡張）
- ruff / pytest

### 既存ファイル構成
```
oyagokoro-backend/
├── app/
│   ├── main.py              # FastAPI 本体（CORS + /api/v1）
│   ├── settings.py          # pydantic-settings
│   ├── database.py          # async engine + get_session
│   ├── models/              # 11 SQLAlchemy モデル（実装済み）
│   ├── api/v1/
│   │   ├── __init__.py      # api_router_v1
│   │   └── health.py        # /api/v1/health
│   └── schemas/             # 空（Phase 1 で Pydantic スキーマ追加）
├── alembic/
│   ├── env.py               # async 対応
│   └── versions/
│       └── c56b822a5394_init.py  # 初回マイグレ（適用済み）
├── tests/
│   ├── conftest.py
│   └── test_health.py
├── docker/init/01_extensions.sql
├── docker-compose.yml
├── pyproject.toml + uv.lock
├── .env.sample
└── README.md
```

### 起動確認

```bash
cd ~/Desktop/workspace/oyagokoro-backend
cp .env.sample .env
docker compose up -d
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

- API ドキュメント: http://localhost:8000/docs
- ヘルスチェック: http://localhost:8000/api/v1/health

---

## 4. 今セッションで進める実装スライス

**詳細は [tmp/kacho_plan_phase1_backend.md](tmp/kacho_plan_phase1_backend.md)（課長作成・必読）**

スライス一覧（要約）:

| ID | スライス名 | 概要 |
|---|---|---|
| B-Slice-1 | 認証基盤 | Firebase Admin SDK + ID Token 検証ミドルウェア + users CRUD |
| B-Slice-2 | カプセル CRUD | capsules 作成・取得・開封日変更 |
| B-Slice-3 | 参加者管理 | members 招待・削除・一覧 |
| B-Slice-4 | 配信先メアド管理 | delivery_addresses CRUD |
| B-Slice-5 | 記録の作成・閲覧 | records POST/GET（1週間ウィンドウ + visibility 適用）|
| B-Slice-6 | 開封フロー | unseal API + 開封日到来バッチ（Vercel Cron）|
| B-Slice-7 | 課金 + ストレージ | Stripe webhook + プラン管理 + ストレージ追加購入 |
| B-Slice-8 | メール配信 | Resend 統合 + 招待 / 開封通知 / 配信メール / バウンス |
| B-Slice-9 | ファイルアップロード | S3 presigned URL + record_attachments（MVP+ 候補）|

実行順序・並列度・依存関係は課長計画書 §B 参照。

---

## 5. 重要な設計判断（既決定事項・変更禁止）

Phase 0 で確定済みの不可変ルール:

1. **主キー**: 全テーブル内部UUID + Firebase UID は users.firebase_uid
2. **users 物理削除禁止**: `is_deleted` で論理削除・退会5年後に `anonymize_scheduled_at` で PII 匿名化
3. **records は INSERT only**: DB トリガで UPDATE/DELETE/TRUNCATE 全て禁止
4. **1週間ウィンドウ**: `records.window_ends_at` 生成列で事前計算（投稿翌日0時JST起算 + 7日）
5. **subscriptions が真実の源**、`users.current_plan` は冗長キャッシュ
6. **配信先は capsules 単位**、参加者全員が共有
7. **storage_usage は capsule 単位**で即時更新（record_attachments INSERT トリガ）
8. **email_deliveries.unseal_event_id は NULL 許容** — `unseal_notice`/`record_delivery` 時のみ必須（CHECK 制約）
9. **email は LOWER 正規化** + 関数インデックス（delivery_addresses / capsule_members 共通）
10. **storage_purchases は 20年永続**・買い切り・取り消し不可・expires_at は BEFORE INSERT トリガーで設定

---

## 6. SQLAlchemy モデル使用上の注意（Phase 0 で確定）

- `app/models/storage_purchase.py` の `expires_at` は **通常カラム + DB トリガーで設定**。Computed ではない。INSERT 時に値指定しないこと（自動設定される）
- `app/models/record.py` の `window_ends_at` は `Computed("timezone('Asia/Tokyo', date_trunc('day', timezone('Asia/Tokyo', posted_at)) + INTERVAL '8 days')", persisted=True)` の生成列。INSERT 時に値指定不可
- ORM モデルには **インデックス・コメント定義が含まれていない**（autogenerate ドリフト残・Phase 2 で解消予定）。autogenerate を再実行すると差分が出るが、それは「DB に存在するインデックス・コメントを ORM が把握していない」だけ。新規テーブル追加時に注意

---

## 7. マイグレーション運用

- 真実の源 = Alembic（モデル + alembic/versions/）
- スキーマ変更時は:
  1. `app/models/` を編集
  2. `uv run alembic revision --autogenerate -m "<変更内容>"`
  3. 生成ファイルを目視確認・必要なら手動補完（インデックス・トリガー・RLS）
  4. `uv run alembic upgrade head`
  5. pytest 通過確認

参考: `oyagokoro/db/schema.sql` v0.4 と `oyagokoro/db/migrations/0001_init.sql` は**実機検証済みの設計リファレンス**（読み物として活用、ただし更新は別途）

---

## 8. 外部サービス連携（B-Slice ごとに発生）

実環境セットアップ手順は [docs/external-services-setup.md](docs/external-services-setup.md) を参照。

社長が並行してアカウント開設・キー取得を進めている想定。`.env` に値を設定してもらってから該当 B-Slice に着手。

| サービス | 必要となる B-Slice |
|---|---|
| Firebase Auth | B-Slice-1 |
| Stripe | B-Slice-7 |
| Resend | B-Slice-8 |
| AWS S3 | B-Slice-9（MVP+ 候補）|

**dev モードのモック方針**: 認証は B-Slice-1 で「ID Token モック切替」を実装し、ローカル開発時は Firebase 不要で動かせるようにする（社長判断推奨論点・課長計画書 §C 参照）。

---

## 9. マルチエージェント組織体制（継続）

Phase 0 と同じ:
- 社長（ユーザー）→ 部長（メイン）→ 課長 / 顧問 / 担当者
- 詳細: [.claude/CLAUDE.md](.claude/CLAUDE.md)
- ダッシュボード: [status/dashboard.md](status/dashboard.md)

### 運用ルール

- **部長は手を動かさない**（実装・コーディング・ファイル編集すべて担当者経由）
- 担当者失敗時も部長が代行せず再ディスパッチ
- 並列ディスパッチ最大化
- 進捗は dashboard.md に随時反映

---

## 10. 権限設定（既設定済み）

`.claude/settings.json` の `permissions.allow`:
- Write / Edit
- Bash(mkdir|ls|cat|test|git|uv|npx|npm|docker:*)

新規コマンドが必要なら社長許可を取って追加。

---

## 11. テスト方針（Phase 1 開始時に確認推奨）

- pytest + pytest-asyncio (asyncio_mode=auto) は設定済み
- httpx + ASGITransport でエンドポイントテスト
- テスト用 DB をどう用意するか（テストごとにロールバック / 別 DB / 同 DB）は B-Slice-1 着手前に決定推奨（課長計画書 §C 参照）

---

## 12. 部長判断が必要な論点（課長計画書 §C より抜粋）

実装前に社長承認推奨:
- Firebase Admin SDK の Service Account JSON 配布方針
- 認証ミドルウェアの dev モックトークン採用
- Vercel Cron Jobs vs GitHub Actions 等のバッチ実装手段
- Stripe webhook の idempotency 設計
- pytest フィクスチャ戦略・DB ロールバック方針
- API バージョニング（/api/v1/ 固定で OK か）
- Sentry / Logger ライブラリ選定
- ファイルアップロード（B-Slice-9）を Phase 1 含めるか Phase 2 か

詳細は [tmp/kacho_plan_phase1_backend.md](tmp/kacho_plan_phase1_backend.md) §C を必読。

---

## 13. Phase 2 申し送り（バックエンド観点・触らない）

顧問記録より（[tmp/komon_setup_review.md](tmp/komon_setup_review.md) 参照）:
- autogenerate ドリフト解消（ORM モデルにインデックス・コメント定義）
- ヘルスチェック 503化（k8s/監視対応）
- email_deliveries パーティション設計
- AC-06 / §9.6 / ★G の DB 層強制トリガー
- subscriptions UNIQUE インデックス二重化整理
- `normalize_email_lower()` トリガーに3テーブル目追加時の拡張コメント

---

## 14. 言葉遣い・運用ルール

- 日本語で応答
- Git コミットメッセージも日本語、`add:` / `fix:` / `update:` / `clean:` / `change:` プレフィックス
- コミットに Co-authored-by 等の trailer は付けない
- `tmp` は常にプロジェクト直下の `./tmp/`
- `.env` は必ず `.gitignore`
- Python は `uv` 管理・`uv run` 実行・`ruff` で lint
- `unknown` 型相当の曖昧な型は使わない（型ヒント徹底）

---

## 15. このセッション開始時の最初の発話例（部長 → 社長）

> Phase 1 バックエンド開発を開始します。Phase 0 完了状態を確認しました（11テーブルのスキーマ + FastAPI 雛形 + Alembic 適用済み）。
> 課長計画書のスライス順序（B-Slice-1 〜 B-Slice-9）に従って実装します。最初の B-Slice-1（認証基盤）から始めますが、Firebase 実環境連携 / 開発用モックトークンのどちらで開始しますか？

---

**END OF PHASE 1 BACKEND KICKOFF PROMPT**

*このプロンプトを起点に、おやごころ MVP のバックエンド実装が始まる。*
