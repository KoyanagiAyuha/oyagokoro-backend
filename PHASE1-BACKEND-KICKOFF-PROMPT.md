# おやごころ Phase 1 バックエンド開発キックオフ プロンプト

> このファイルは Phase 1 バックエンド開発専用の新セッション開始時に最初に読み込ませるプロンプトです。
> **改訂: 2026-07-03 / IAP・モバイル整合・Critic REVISE 反映 + 着手前論点（§12）のエンジニア決定反映**（初版: Phase 0 完了時点 2026-05-27）。
> 方針変更（課金 = Apple/Google IAP 確定、フロントエンド = iOS/Android ネイティブ確定。Web フロントエンド提供・Next.js・Stripe は不採用）を全面反映し、スライス構成を再編した。
> **バックエンドのホスティング先は Vercel に決定**（2026-07-03・§12-1）。Python/Docker ランタイムに対応済みであり、フロントエンドがネイティブアプリで Web フロントを持たない場合でも、Vercel は backend API のホスト先として採用する（上記「Web フロントエンド提供…不採用」は Next.js 等による Web アプリ提供を指し、backend API のホスティング可否とは別軸）。
> フロントエンド（モバイルアプリ）開発は別セッションで進行。

---

## 0. このセッションのゴール

**Phase 1 バックエンド: 本書 §4 のスライス順序（B1〜B9 本流 + P1〜P3 IAP並列トラック）に従って API を段階実装。**

各スライスごとに「動く API 群」を pytest + curl で疎通確認しながら積み上げる。モバイルアプリは別セッションで並行進行（実 API を順次叩く想定）。

---

## 1. プロジェクト概要（要約）

- **名称**: おやごころ（lydear エコシステム第1弾）
- **コンセプト**: 家族の20年タイムカプセル（思想を強制せず、設定で柔軟）
- **フロントエンド**: iOS / Android ネイティブアプリ（Web フロントは提供しない）
- **課金**: Apple App Store IAP + Google Play IAP（Stripe は不採用）
- **API ベース URL（予定）**: `https://api.oyagokoro.lydear.com/api/v1/`（api-spec §1.1）。**ホスティング先は Vercel に確定**（2026-07-03・§12-1）。`api.oyagokoro.lydear.com` は Vercel 上で稼働する FastAPI アプリ（Python/Docker ランタイム）に割り当てるカスタムドメインであり、静的コンテンツの配信 URL ではなく API ホストそのものを指す

**正典（このリポジトリ内・必読）**:

| 文書 | 役割 |
|---|---|
| [docs/product-spec.md](docs/product-spec.md) | 製品仕様（状態遷移・業務ルール・AC・IAP/モバイル最新化 v1.0） |
| [docs/api-spec.md](docs/api-spec.md) | API エンドポイント仕様（全28EP + エクスポート2EP） |
| [docs/data-model.md](docs/data-model.md) | データモデル（12テーブル・IAP反映版。2026-07-03: `export_jobs` 追加） |
| [docs/api-conventions.md](docs/api-conventions.md) | API 共通規約 |
| [docs/owner-setup-guide.md](docs/owner-setup-guide.md) | 外部サービスの社長側セットアップ手順 |

> 旧仕様（`specs/oyagokoro-spec.md`、Web/Vercel 前提の記述、Stripe 課金）への参照はすべて廃止。仕様の裏取りは上記 docs/ のみを使う。

---

## 2. このセッションが触るリポジトリ

`/Users/ayuhakoyanagi/Desktop/workspace/oyagokoro-backend/`

独立 git リポジトリ。Phase 0 完了時点で `074ada9` 初回コミット済み。その後 `5267672` で Phase 1 認証基盤・データモデル IAP 整合・仕様ドキュメント（docs/）を整備済み。

**触らないリポジトリ**:
- モバイルアプリ（iOS / Android）のリポジトリ — アプリ側セッションの担当範囲

---

## 3. Phase 0 で完成済みのもの（再確認）

### 技術スタック
- FastAPI + uv 管理（Python 3.12）
- SQLAlchemy 2.x async + Alembic
- PostgreSQL 16（ローカル開発は Docker Compose + pgcrypto 拡張。本番は Neon を想定）
- ruff / pytest

### 既存ファイル構成
```
oyagokoro-backend/
├── app/
│   ├── main.py              # FastAPI 本体（/api/v1）
│   ├── settings.py          # pydantic-settings
│   ├── database.py          # async engine + get_session
│   ├── models/              # 11 SQLAlchemy モデル（実装済み）
│   ├── api/v1/
│   │   ├── __init__.py      # api_router_v1
│   │   └── health.py        # /api/v1/health
│   └── schemas/             # Pydantic スキーマ（Phase 1 で拡充）
├── alembic/
│   ├── env.py               # async 対応
│   └── versions/            # マイグレーション（適用済み）
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
# リポジトリ直下で
cp .env.sample .env
docker compose up -d
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

- API ドキュメント: http://localhost:8000/docs
- ヘルスチェック: http://localhost:8000/api/v1/health

---

## 4. 今セッションで進める実装スライス（改訂版）

旧 B-Slice-1〜9（Stripe 前提の旧構成）は廃止し、以下に差し替える。実行順序・並列トラックは表末尾の依存グラフ参照。

### 本流スライス

| ID | 名称 | 狙い（1行） | 主要エンドポイント / テーブル | 依存 | 区分 |
|---|---|---|---|---|---|
| **B1** | 認証仕上げ | 実装済み認証基盤（register / me / 規約同意）にプロフィール更新を足してユーザーリソースを完成させる | `PATCH /users/me`（api-spec §2.3）/ `users` | — | MVP |
| **B2** | カプセル CRUD | カプセル作成・一覧・詳細・開封日変更を通し、全リソースの土台を作る | api-spec §3.1〜3.4 / `capsules`, `capsule_members`（作成者行） | B1 | MVP |
| **B3** | メール基盤（前倒し） | Resend クライアント + `email_deliveries` 書込 + テンプレート + dev モックを共通基盤として先に整備する | 外部 EP なし（内部基盤）/ `email_deliveries` | B2 | MVP |
| **B4** | 参加者管理 | 招待メール送信〜受諾〜削除/退出。**招待トークン設計込み**（§12-3 の仕様の穴を先に解消） | api-spec §4.1〜4.4 / `capsule_members` | B2, B3 | MVP |
| **B5** | 配信先メアド管理 | 配信先 CRUD（タグ・LOWER 正規化・上限5） | api-spec §5.1〜5.4 / `delivery_addresses` | B2 | MVP |
| **B6** | 記録（4状態可視性） | records 3EP。**表示レベルリゾルバ（自分/ウィンドウ中/封印中/開封済み）を開封前提込みで最初から実装**（api-spec §6.2。後付けするとリゾルバを作り直す羽目になる）+ 月次ソフトブロック | api-spec §6.1〜6.3 / `records` | B2 | MVP |
| **B7** | 退会（論理削除） | `DELETE /users/me`。副作用が参加者遷移・配信先 SET NULL に跨るため独立スライス | api-spec §2.5 / `users`, `capsule_members`, `delivery_addresses` | B4, B5 | MVP |
| **B8** | 開封 + バッチ + 配信 | 手動開封（confirmation_token 発行込み・§12-4）+ 開封日到来バッチ + 配信オーケストレーション（visibility×tag フィルタ・skipped 証跡・バウンスリトライ・open_at_change 通知の有効化。通知はメールのみ・§12-5） | api-spec §3.5〜3.6・§9.1/9.2、`POST /internal/jobs/*`（Vercel Cron から起動・§12-2）/ `unseal_events`, `email_deliveries` | B3, B5, B6 | MVP |
| **B9** | エクスポート（新設） | **MVP 必須**（product-spec §4.1・AC-11・社会契約宣言「データ完全エクスポート権」）。非同期ジョブ（202受理）+ ジョブ状態 + S3 presigned GET + PDF/A-1b 生成 | api-spec §6.4/6.5 / `export_jobs` テーブル（新設決定・data-model.md §3.12・§12-9） | B6（+ S3 セットアップ） | MVP |

- B8 は規模次第で **B8a（手動開封 API + confirmation_token）/ B8b（開封日バッチ + 配信 + バウンス）** の2分割を許容する。
- B2 の開封日変更通知（`open_at_change`）は B3 完了までキュー登録のスタブで良い（B8 で配信を有効化）。

### 並列トラック（IAP。本流と独立に進行可）

| ID | 名称 | 狙い（1行） | 主要エンドポイント / テーブル | 依存 | 区分 |
|---|---|---|---|---|---|
| **P1** | IAP 購入検証 + 購読状態 | サブスク購入のサーバー検証（クライアント申告を信用しない）+ 購読状態/利用枠の取得 | `POST /billing/iap/verify`・`GET /billing/subscription`（api-spec §7.1/7.2）/ `subscriptions` | B1 | MVP |
| **P2** | IAP ウェブフック | Apple ASSN V2 + Google RTDN（Pub/Sub push + OIDC 検証）の2系統 + 状態同期 + `current_plan` 再計算 + `latest_notification_at` 単調ガード + purchaseToken ローテーション追跡（data-model §4.7） | `POST /webhooks/apple/notifications`・`POST /webhooks/google/rtdn`（api-spec §7.4/7.5）/ `subscriptions`, `users` | P1, ホスティング確定（§12-1） | MVP |
| **P3** | トライアル終了リマインダー | 3日前・1日前リマインダー + 終了検知のバッチ小スライス（product-spec §6.5・api-spec §9.2）。MVP はメールのみ（§12-5） | 内部ジョブ / `subscriptions`, `email_deliveries`（※ email_type 追加が必要・§12-3注参照） | P2, B3 | MVP |

### 後送スライス

| ID | 名称 | 狙い（1行） | 主要エンドポイント / テーブル | 依存 | 区分 |
|---|---|---|---|---|---|
| **M1** | 添付 + 消費型ストレージ | S3 presigned PUT 直アップロード + 完了通知 + **追加ストレージ 10GB 消費型 IAP**（添付が無いと購入動機が無いため同時期に実装） | api-spec §8.1/8.2・§7.3 / `record_attachments`, `storage_usage`, `storage_purchases` | B6, P1 | MVP+ |

- **匿名化バッチ**（退会 +5年の PII 匿名化・data-model §4.3）は運用開始から5年間発火しないため **Phase 2 送り**と明記する。

### 依存グラフ（並列度）

```
本流:   B1 → B2 → B3 → B4 ─┐
              ├────────→ B5 ─┼→ B7 → B8 → B9
              └────────→ B6 ─┘
IAP:    B1 → P1 → P2 → P3        （本流と独立・随時並列）
MVP+:   {B6, P1} → M1
```

- 最大並列: B4 / B5 / B6 の3本 + IAP トラック。同一テーブルを触るスライスは直列にしてある（B7 は B4/B5 の後、B8 は B3/B5/B6 の後）。

---

## 5. 重要な設計判断（既決定事項・変更禁止）

確定済みの不可変ルール（IAP 反映で表現を最新化）:

1. **主キー**: 全テーブル内部UUID + Firebase UID は users.firebase_uid
2. **users 物理削除禁止**: `is_deleted` で論理削除・退会5年後に `anonymize_scheduled_at` で PII 匿名化
3. **records は INSERT only**: DB トリガで UPDATE/DELETE/TRUNCATE 全て禁止
4. **1週間ウィンドウ**: `records.window_ends_at` 生成列で事前計算（投稿翌日0時JST起算 + 7日）
5. **subscriptions が真実の源、`users.current_plan` は冗長キャッシュ** — ただし subscriptions 自体は **Apple/Google ストア購読状態のミラー**（真実の源はストア側）。Stripe 的な顧客IDは存在せず、ユーザー↔購読の紐付けは購読識別子（Apple `original_transaction_id` / Google `purchase_token`）→ `user_id` の逆引きが権威（data-model §3.7・§4.7）
6. **配信先は capsules 単位**、参加者全員が共有
7. **storage_usage は capsule 単位**で即時更新（record_attachments INSERT トリガ）
8. **email_deliveries.unseal_event_id は NULL 許容** — `unseal_notice`/`record_delivery` 時のみ必須（CHECK 制約）
9. **email は LOWER 正規化** + 関数インデックス（delivery_addresses / capsule_members 共通）
10. **storage_purchases は 20年永続・買い切り**・expires_at は BEFORE INSERT トリガーで設定。原則不変だが、**消費型 IAP の返金時のみ `revoked_at` の更新を許可**（行は物理削除しない。有効量集計から除外。data-model §3.8）

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

参考: 設計リファレンスは [docs/data-model.md](docs/data-model.md)（DDL・インデックス・CHECK 制約・トリガー方針を網羅）。

---

## 8. 外部サービス連携（スライスごとに発生）

実環境セットアップ手順は [docs/owner-setup-guide.md](docs/owner-setup-guide.md) を参照。社長が並行してアカウント開設・キー取得を進めている想定。`.env` に値を設定してもらってから該当スライスに着手。

| サービス | 用途 | 必要スライス | 備考 |
|---|---|---|---|
| **Vercel（ホスティング）** | バックエンド API 本体のホスティング先。Python/Docker ランタイムに対応 | 全スライス | **決定済み（2026-07-03・§12-1）**。フロントはネイティブアプリで Web フロントは提供しないが、backend host としては Vercel を採用。`api.oyagokoro.lydear.com`（§1）をカスタムドメインとして割り当てる |
| Firebase Auth | ID Token 検証（Google / Apple Sign-In） | B1（基盤導入済み） | dev モック切替あり（下記） |
| Resend | メール送信（`noreply@lydear.com`・バウンス Webhook） | B3 | ドメイン認証（SPF/DKIM）が先行 |
| App Store Server API + ASSN V2 | Apple 購入検証・購読通知 | P1 / P2 | ASSN V2 の通知先 URL は**公開 HTTPS 必須**（Vercel の公開エンドポイント/カスタムドメインを使用） |
| Google Play Developer API + Cloud Pub/Sub | Google 購入検証・RTDN | P1 / P2 | Pub/Sub トピック + push サブスクリプション（OIDC トークン付与）の構築が必要。**Vercel でホスティングしても GCP Pub/Sub 自体は必須のまま**（RTDN は Google 側仕様で Pub/Sub 経由必須）。push サブスクリプションの宛先を Vercel 上の webhook URL（`POST /webhooks/google/rtdn`）に向ける構成とする（Pub/Sub 依存は残る。2026-07-03 注記） |
| AWS S3 | エクスポート生成物の配布（B9）/ 添付実体（M1） | **B9（MVP へ繰り上げ）**, M1 | エクスポートが MVP 必須化したため **S3 は MVP+ → MVP へ繰り上げ** |
| Vercel Cron（スケジューラ） | 内部ジョブ EP `POST /internal/jobs/*`（共有シークレットヘッダで保護）の定期起動 | B8, P3 | **決定済み（2026-07-03・§12-2）**。外部スケジューラ（Cloud Scheduler / GitHub Actions cron 等）は不採用 |

**注記**:
- **社長側セットアップは Stripe 時代より重い**（App Store Connect の In-App Purchase 構成 + ASSN V2 URL 登録、Google Play Console + GCP サービスアカウント + Pub/Sub、の両ストア分）。着手が遅れると P1/P2 がブロックするため早期に依頼する。
- **webhook 公開 URL（Apple 通知先・Pub/Sub push 先）はホスティング決定済み（Vercel・§12-1）に伴い、Vercel のデプロイ URL / カスタムドメインを使用する**。P1/P2 実装時に Apple Developer / GCP Console 側へ実際の URL を登録する。

**dev モードのモック方針**: 認証は「ID Token モック切替」で、ローカル開発時は Firebase 不要で動かせるようにする（導入済み方針を維持）。メール（B3）も dev ではモック送信（ログ + email_deliveries 書込のみ）とする。

---

## 9. マルチエージェント組織体制（継続）

- 社長（ユーザー）→ リード（Orchestrator）→ Planner / Critic / Worker
- リードは手を動かさない（実装・コーディング・ファイル編集は Worker 経由）
- Worker 失敗時もリードが代行せず再ディスパッチ
- 並列ディスパッチ最大化（§4 の依存グラフに従う。同一ファイルは1 Worker のみ）
- 設計判断が分かれる論点（§12）は実装前に Critic レビューへ回す

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
- テスト用 DB 戦略は **Docker 上の PostgreSQL に対しテストごとトランザクションロールバック**を既定案とする（§12-8。生成列・トリガー・CHECK 制約の検証が必要なため SQLite 代替は不可）
- IAP（P1/P2）はストア API クライアントをインターフェース化し、署名検証・状態導出マッピング（data-model §3.7 の表）をフィクスチャ JWS / モックレスポンスで網羅する

---

## 12. 着手前に決めるべき論点（優先度順・推奨既定案付き）

実装前に社長承認推奨。**(1)(2)(5)(6)(7)(8)(9)(10) は 2026-07-03 にエンジニア決定として確定した**（下記の該当項目を参照）。**(3)(4) は仕様書側の穴だったが、同日 data-model.md / api-spec.md へ追記済み**（下記の該当項目を参照）。本セクションの論点はすべて決定済みであり、Phase 1 着手をブロックする未解決論点は残っていない。

1. **API ホスティング先** — **決定済み（2026-07-03）: Vercel**。Python/Docker ランタイムに対応済みであり、フロントエンドがネイティブアプリ（Web フロントを持たない）であっても、Vercel を backend API のホスト先として採用する。webhook 公開 URL（Apple ASSN V2 の通知先 / Google Pub/Sub push 先）は Vercel 上の公開 HTTPS エンドポイントを用いる（§8 参照）。長時間ジョブ（エクスポート生成・配信バッチ）はサーバーレス関数の実行時間制約と相性が悪い点に留意し、内部ジョブ EP（`/internal/jobs/*`）はバッチを短時間で完了できる粒度に分割するか、キュー投入 + 非同期処理で対応する（詳細は実装スライス B8/B9 で設計）。
2. **バッチ実行基盤** — **決定済み（2026-07-03）: Vercel Cron が認証付き内部ジョブ EP `POST /internal/jobs/*`（共有シークレットヘッダで保護）を定期的に叩く構成**。ホスティングが Vercel に確定したため、同一スタック内で完結する Vercel Cron を採用し、外部スケジューラ（Cloud Scheduler / GitHub Actions cron 等）は不要。開封検知は `unsealed_at IS NULL AND open_at <= now()` の冪等ガード（data-model §5.2）があるため±数分精度で足りる。
3. **招待トークン設計（仕様の穴）** — `POST /invitations/{token}/accept` はあるが、**`capsule_members` にトークンカラムが存在しない**。**追記済み（data-model.md / api-spec.md の該当節参照）**: `capsule_members` に `invite_token_hash`（ハッシュ保存）+ `invite_token_expires_at`（有効期限）カラムを追加する方針を data-model.md §3.3（ER図・カラム定義・CHECK・索引）に反映し、api-spec.md §4.2（招待作成時の一度限りトークン発行）・§4.4（受諾時のハッシュ突合）に追記した。DB カラムの実追加（マイグレーション）は未実施で、実装スライス（B4）で行う。
   ※関連する仕様の穴（3件目）: P3 のトライアルリマインダーを `email_deliveries` に記録する場合、`email_type` CHECK（5種）に該当種別が無い。**追記済み（data-model.md 参照）**: `email_type` CHECK に `'trial_reminder'` を追加し（6種に拡張）、`unseal_event_id` NULL許容CHECKにも整合させた（data-model.md §3.11・§4.5.1・§6.12）。
4. **開封 confirmation_token の発行経路（仕様の穴）** — api-spec §3.5 は `confirmation_token`（サーバー発行の短命トークン）を必須とするが、**発行エンドポイントが §11 一覧に存在しない**。**追記済み（api-spec.md の該当節参照）**: `POST /capsules/{id}/unseal/prepare` を api-spec.md §3.5 として新設し（TTL 5分・単回使用）、既存の開封本 API は §3.6 に繰り下げて二段階フローを明記した。§11 エンドポイント一覧・§10 エラーコード一覧（`ERR_CONFIRMATION_TOKEN_INVALID` / `ERR_CONFIRMATION_TOKEN_EXPIRED`）にも反映済み。
5. **プッシュ通知の MVP スコープ** — **決定済み（2026-07-03）: MVP はメールのみに縮退する。FCM / APNs によるプッシュ通知は MVP+ 以降に送る**。開封日変更通知・トライアルリマインダー等はすべて `email_deliveries` 経由のメール配信で実現する（product-spec 側の期待値調整は社長確認済み）。
6. **appAccountToken の扱い** — **決定済み（data-model §3.1・§4.7 で既決、2026-07-03 に本書へ転記）**: Apple `appAccountToken` / Google `obfuscatedExternalAccountId` は初回紐付けのヒントに過ぎず、権威は購読識別子（`original_transaction_id` / `purchase_token`）→ `user_id` の DB 逆引きに置く。実装時（P1/P2）にこの規約から逸脱しないこと。
7. **sandbox / production 混線のテスト戦略** — **決定済み（2026-07-03）: ストアクライアント（Apple/Google の検証 API 呼び出し部分）をインターフェース化してモックし、pytest はモック経由でユニット/結合テストを行う。sandbox 環境に対する実クライアントでの手動検証は別途運用で行い、自動テストのスコープには含めない**。`environment` カラムで sandbox/production を保持し、本番エンタイトルメント判定は `production` を要求（data-model §3.7）。sandbox 購入で本番権利が付かないことのテストケースは P1/P2 の受け入れ条件に含める。
8. **pytest の DB 戦略** — **決定済み（2026-07-03）: Docker PostgreSQL に対しテストごとにトランザクション + ロールバック**（§11 と同一方針）。生成列（`window_ends_at`）・トリガー（INSERT only / expires_at / storage_usage）・CHECK 制約の検証が必要なため SQLite 代替は不可。
9. **エクスポートジョブの永続化** — **決定済み（2026-07-03）: `export_jobs` テーブルを新設し、ジョブ状態（`status`）・要求者（`requested_by`）・生成物の S3 キー（`object_keys`）・失敗時 `error_message`・有効期限（`expires_at`）を永続化する**（data-model.md §3.12・api-spec.md §6.4/§6.5）。サーバー/ワーカーの再起動をまたいでもジョブ状態は失われない。
10. **`processed_notifications` テーブルの要否** — **決定済み（2026-07-03）: MVP では作らない**。IAP 通知の冪等性は「購読識別子 UNIQUE + `latest_notification_at` の単調ガード + `INSERT ... ON CONFLICT DO NOTHING`」で担保する（data-model §6.14 の既決を追認）。専用の重複排除テーブルは Phase 2 で要否を再検討する（§13 申し送り）。

---

## 13. Phase 2 申し送り（バックエンド観点・触らない）

- autogenerate ドリフト解消（ORM モデルにインデックス・コメント定義）
- ヘルスチェック 503化（監視対応）
- email_deliveries パーティション設計
- AC-06 / 参加者・配信先上限（★G）の DB 層強制トリガー（data-model §6.11）
- subscriptions UNIQUE インデックス二重化整理
- `normalize_email_lower()` トリガーに3テーブル目追加時の拡張コメント
- **PII 匿名化バッチ**（退会 +5年・data-model §4.3。運用開始5年間は発火しないため Phase 2）
- `processed_notifications` テーブルの要否再検討（data-model §6.14。MVP は冪等 UPSERT + 単調ガード + UNIQUE で代替）

---

## 14. 言葉遣い・運用ルール

- 日本語で応答
- Git コミットメッセージも日本語、`add:` / `fix:` / `update:` / `clean:` / `change:` プレフィックス
- コミットに Co-authored-by 等の trailer は付けない
- `tmp` は常にプロジェクト直下の `./tmp/`
- `.env` は必ず `.gitignore`
- Python は `uv` 管理・`uv run` 実行・`ruff` で lint
- 型ヒント徹底（曖昧な型を使わない）

---

## 15. このセッション開始時の最初の発話例（リード → 社長）

> Phase 1 バックエンド開発を開始します。認証基盤（B1 の大半）と 11 テーブルのスキーマは実装済みです。
> 改訂版スライス（B1〜B9 本流 + P1〜P3 IAP 並列トラック、§4）に従って進めます。§12 の着手前論点はすべて 2026-07-03 に決定済み（ホスティング=Vercel / バッチ=Vercel Cron / プッシュ=メールのみ縮退 / エクスポート永続化=export_jobs 等）で、仕様の穴3件（招待トークン・confirmation_token 発行 EP・trial_reminder 種別）も docs へ追記済みのため、Phase 1 着手をブロックする未解決論点はありません。
> 実装は B1 仕上げ（PATCH /users/me）→ B2 カプセル CRUD から始めます。

---

**END OF PHASE 1 BACKEND KICKOFF PROMPT**

*このプロンプトを起点に、おやごころ MVP のバックエンド実装が始まる。*
