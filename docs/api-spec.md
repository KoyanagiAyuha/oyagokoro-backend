# おやごころ API エンドポイント仕様書

> Backend (FastAPI) ⇔ モバイルネイティブアプリ (iOS / Android) の権威ある API 定義。
> 作成日: 2026-07-02 / 担当: 仕様固めフェーズ
> 位置づけ: バックエンド API の中核仕様。`api-conventions.md`（共通規約）と `data-model.md`（データモデル）を土台に、リソースごとのエンドポイントを「理想形」で定義する。
> スコープ: MVP 全リソース + MVP+（添付ファイル）。実装済み/未実装の区別は書かない（あるべき姿のみ）。

---

## 1. メタ情報

### 1.1 ベース

| 項目 | 値 |
|---|---|
| ベースパス | `/api/v1/`（全エンドポイント共通プレフィックス） |
| ローカル開発 | `http://localhost:8000/api/v1/` |
| 本番（予定） | `https://api.oyagokoro.lydear.com/api/v1/` |
| Content-Type | `application/json`（アップロード実体は S3 直 PUT。詳細 §8） |
| 文字コード | UTF-8 |
| 日時表現 | ISO 8601 / TIMESTAMPTZ（例: `2046-03-15T00:00:00+09:00`）。DB は UTC 保存・返却時 JST |
| クライアント | iOS / Android ネイティブ（Origin ヘッダーなし。CORS は開発ツール向けのみ維持） |

### 1.2 認証

すべての保護エンドポイントは Firebase Auth の ID Token を Bearer で送信する。

```
Authorization: Bearer <Firebase ID Token>
```

- ID Token はモバイルアプリの Firebase Auth SDK（Google Sign-In / Sign in with Apple）で取得する。
- バックエンドは `verify_id_token()` で検証し、`uid`（= `users.firebase_uid`）と `email` を取り出す。Google / Apple どちらのプロバイダでも同一パス。
- `email` が欠落したトークン（Apple「Hide My Email」で relay も無い等の異常系）は `400 ERR_INVALID_TOKEN` で拒否する。relay email（`@privaterelay.appleid.com`）は許容する。
- 認証不要なのは `GET /health`・IAP Webhook（`/webhooks/*`。ストア署名で検証）・招待受諾（`/invitations/{token}/accept` は招待トークンで認可）のみ。

### 1.3 認可の基本モデル

- **カプセル参加者権限は完全民主制**（product-spec.md §5.3）。創設者・招待者の区別なし。あるカプセルに対する操作は、原則「そのカプセルの `active` な参加者」であれば全員が可能。
- カプセル配下リソース（members / delivery-addresses / records）へのアクセスは「リクエスト元ユーザーが対象カプセルの `active` 参加者であること」を必須とする。非参加者は `403 ERR_NOT_CAPSULE_MEMBER`。
- 開封済み（`unsealed_at` 非 NULL）カプセルは「読む期間」に遷移し、一部の書き込み操作が状態矛盾（`409`）になる（§各リソース参照）。

### 1.4 共通エラー形式

`api-conventions.md` §7 に準拠。全エラーは以下の形式で返す。

```json
{
  "detail": "人が読めるエラーメッセージ",
  "code": "ERR_XXX"
}
```

- `detail`: 人間可読の説明（多言語化はクライアント側で `code` を用いて行う想定）。
- `code`: 機械可読のエラーコード（`ERR_` プレフィックス）。一覧は §10。
- FastAPI バリデーション由来（`422`）は FastAPI デフォルト形式（`detail` が配列）になり得る。クライアントは `422` を「入力形式エラー」として汎用ハンドリングする。

### 1.5 ステータスコード方針（api-conventions §6 準拠）

| コード | 用途 |
|---|---|
| 200 | 取得・更新成功 |
| 201 | 作成成功 |
| 202 | 受理（非同期処理を開始。Webhook 等） |
| 204 | 削除成功・本文なし |
| 400 | 入力値・トークン不正 |
| 401 | 認証失敗・トークン期限切れ |
| 403 | 権限なし（非参加者・凍結カプセル等） |
| 404 | リソース未存在（または権限秘匿のための未存在偽装） |
| 409 | 状態矛盾（開封済み・重複・上限到達等） |
| 402 | 課金要求（無料枠超過のソフトブロック。§7.1 参照） |
| 422 | バリデーションエラー（FastAPI デフォルト） |
| 500 | サーバーエラー |

> **上限系のコード選択**: 「無料枠の月次記録上限（5件）」超過は課金誘導が主目的のため **`402 Payment Required`**（`ERR_MONTHLY_QUOTA_EXCEEDED`）を返す。「有料枠の月次上限（200件）」超過は課金では解決しない“来月リセット”系のため **`409 Conflict`**（`ERR_MONTHLY_LIMIT_REACHED`）を返す。参加者数・配信先数の上限も枠の性質上 **`409`**（`ERR_*_LIMIT_REACHED`）を用いる。

---

## 2. 認証 / ユーザー

### 2.1 `POST /auth/register` — 初回同期（冪等）

Firebase Auth でサインイン成功後、アプリが最初に呼ぶ。ID Token の `uid` / `email` からユーザー行を冪等 UPSERT する。

- **認可**: 有効な ID Token（ユーザー行の存在は不要）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `display_name` | string \| null | 任意 | max 120 | 表示名。未設定可 |
| `locale` | string | 任意 | max 10, 既定 `ja` | BCP-47 |
| `timezone` | string | 任意 | max 64, 既定 `Asia/Tokyo` | IANA tz |

- `firebase_uid` / `email` はボディに含めない（トークンから取得）。既存ユーザーの場合 `display_name` 等はボディで上書きしない（既存値を維持）。

- **レスポンス**: `201 Created`（新規・既存いずれも `UserRead` を返す。冪等）

```json
{
  "id": "3f1c...UUID",
  "firebase_uid": "abc123FirebaseUid",
  "email": "mother@example.com",
  "display_name": null,
  "locale": "ja",
  "timezone": "Asia/Tokyo",
  "current_plan": "free",
  "trial_ends_at": null,
  "terms_agreed_at": null,
  "terms_version": null,
  "created_at": "2026-07-02T10:00:00+09:00",
  "updated_at": "2026-07-02T10:00:00+09:00"
}
```

- **主なエラー**: `400 ERR_INVALID_TOKEN`（email 欠落）/ `401 ERR_UNAUTHENTICATED`（トークン不正・期限切れ）

### 2.2 `GET /users/me` — 自分の情報取得

- **認可**: 認証済みユーザー。`terms_agreed_at = null` でも `200` で返す（規約同意誘導はクライアント判断）。
- **レスポンス**: `200`（`UserRead`。2.1 と同形）
- **主なエラー**: `401 ERR_UNAUTHENTICATED` / `404 ERR_USER_NOT_FOUND`（`register` 未実行）

### 2.3 `PATCH /users/me` — プロフィール更新

- **認可**: 認証済みユーザー本人。
- **リクエストボディ**（すべて任意・指定項目のみ更新）:

| 項目 | 型 | バリデーション |
|---|---|---|
| `display_name` | string \| null | max 120 |
| `locale` | string | max 10 |
| `timezone` | string | max 64（IANA tz） |

- **レスポンス**: `200`（更新後 `UserRead`）
- **主なエラー**: `401 ERR_UNAUTHENTICATED` / `404 ERR_USER_NOT_FOUND` / `422`（不正 tz 等）

### 2.4 `POST /users/me/terms-agreement` — 利用規約同意

利用規約への同意を記録する。`terms_agreed_at` と `terms_version` を同時更新（CHECK `terms_both_or_none` 整合）。バージョンアップ時の再同意にも用いる（冪等・毎回 `terms_agreed_at` を最新化）。

- **認可**: 認証済みユーザー本人。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `terms_version` | string | 必須 | min 1 / max 32 | 同意した規約バージョン（例 `2026-05-26`） |

- **レスポンス**: `200`（更新後 `UserRead`。`terms_agreed_at` / `terms_version` が設定される）
- **主なエラー**: `401 ERR_UNAUTHENTICATED` / `422`（version 空）

### 2.5 `DELETE /users/me` — 退会（論理削除）

物理削除は行わない（社会契約宣言・data-model §4.3）。`is_deleted = true`・`deleted_at`・`anonymize_scheduled_at`（退会 +5 年目安）を設定する。本人が書いた記録は永続保持され、開封日に配信される。

- **認可**: 認証済みユーザー本人。
- **副作用**:
  - 参加中の全カプセルの `capsule_members` を `status='deleted'`・`deletion_reason='self_exit'` に遷移（`display_name_override` に表示名スナップショット）。記録は「元参加者」表記で保持。
  - 本人が `added_by` の配信先メアドは `added_by` を `SET NULL`（メアド自体は残す）。product-spec.md §5.3 の「削除者のメアドが配信先に登録されていれば配信先からも自動除外」はメアド一致で別途処理。
  - 有料購読中の場合、`subscriptions` 行は残す（IAP 解約はストア側操作。当方 DB は監査のため保持）。
- **レスポンス**: `204 No Content`
- **主なエラー**: `401 ERR_UNAUTHENTICATED` / `404 ERR_USER_NOT_FOUND`

---

## 3. カプセル

`CapsuleRead` 共通形:

```json
{
  "id": "cap_UUID",
  "name": "田中家のタイムカプセル",
  "open_at": "2046-03-15T00:00:00+09:00",
  "unsealed_at": null,
  "unseal_trigger": null,
  "is_frozen": false,
  "created_by": "usr_UUID",
  "member_count": 2,
  "my_membership": { "member_id": "mem_UUID", "status": "active" },
  "created_at": "2026-07-02T10:05:00+09:00",
  "updated_at": "2026-07-02T10:05:00+09:00"
}
```

- `unsealed_at = null` = 封印中、値あり = 開封済み。`is_frozen` は `active` 参加者 0 人の凍結状態（product-spec.md §5.6、`capsules` にフラグは持たずクエリ判定）。

### 3.1 `POST /capsules` — 初回セットアップ（カプセル作成）

タイムカプセルを新規作成する。作成者は自動的に `active` 参加者になる。開封日（`open_at`）は必須・スキップ不可（★H）。

- **認可**: 認証済みユーザー。規約同意（`terms_agreed_at` 非 NULL）を必須とする（未同意は `403 ERR_TERMS_NOT_AGREED`）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `name` | string | 必須 | 1–255 | カプセル名 |
| `open_at` | string(date-time) | 必須 | 未来日時（`> now`） | 開封日。過去日時は `422` |

- **レスポンス**: `201`（`CapsuleRead`。作成者が `created_by` かつ `active` メンバーとして登録される）
- **主なエラー**: `401` / `403 ERR_TERMS_NOT_AGREED` / `422 ERR_OPEN_AT_IN_PAST`（過去日）

### 3.2 `GET /capsules` — 自分の参加カプセル一覧

リクエスト元ユーザーが `active` 参加しているカプセルを返す（`status='deleted'` のカプセルは除外）。

- **認可**: 認証済みユーザー。
- **クエリパラメータ**: `state`（任意, `sealed` / `unsealed` / `all`。既定 `all`）
- **レスポンス**: `200`

```json
{ "items": [ { "...CapsuleRead": "..." } ], "total": 1 }
```

- **主なエラー**: `401`

### 3.3 `GET /capsules/{capsuleId}` — カプセル詳細

- **パスパラメータ**: `capsuleId`（UUID）
- **認可**: 対象カプセルの `active` 参加者。非参加者は `404 ERR_CAPSULE_NOT_FOUND`（存在秘匿）。
- **レスポンス**: `200`（`CapsuleRead`）
- **主なエラー**: `401` / `404 ERR_CAPSULE_NOT_FOUND`

### 3.4 `PATCH /capsules/{capsuleId}/open-date` — 開封日変更

開封日を変更する。**参加者全員が変更可能**（product-spec.md §4.1・§5.6）。変更時は全参加者へ通知（`email_type='open_at_change'`・プッシュ）。開封済みカプセルは変更不可。

- **パスパラメータ**: `capsuleId`
- **認可**: 対象カプセルの `active` 参加者（全員可）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション |
|---|---|---|---|
| `open_at` | string(date-time) | 必須 | 未来日時（`> now`） |

- **レスポンス**: `200`（更新後 `CapsuleRead`）。副作用として全 `active` 参加者宛の `open_at_change` 通知を非同期キューに登録。
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404` / `409 ERR_CAPSULE_ALREADY_UNSEALED`（開封済み） / `422 ERR_OPEN_AT_IN_PAST`

### 3.5 `POST /capsules/{capsuleId}/unseal/prepare` — 開封確認トークン発行（2026-07-03 追記）

手動開封（§3.6）の第一段階。クライアントは開封確認モーダルを表示する直前に本 EP を呼び、サーバーが短命の `confirmation_token` を発行する。この EP 自体は開封を実行しない（副作用なし・冪等ではない毎回新規発行）。

- **パスパラメータ**: `capsuleId`
- **認可**: 対象カプセルの `active` 参加者（全員可）。凍結カプセル（`active` 0 人）は発行不可（`403 ERR_CAPSULE_FROZEN`）。
- **リクエストボディ**: なし
- **仕様**:
  - サーバーは `capsule_id` と実行者（`user_id`）に紐付く不透明な `confirmation_token` を生成する。TTL 5 分・単回使用（§3.6 での検証成功時に失効させる）
  - 開封済みカプセルへの発行は不可（`409 ERR_CAPSULE_ALREADY_UNSEALED`）
  - 発行した `confirmation_token` はサーバー側で保持し、§3.6 の検証時にカプセルID・実行者・TTL・未使用であることを照合する
- **レスポンス**: `201 Created`

```json
{
  "confirmation_token": "opaque_confirmation_token_string",
  "expires_at": "2046-03-14T22:05:00+09:00"
}
```

- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `403 ERR_CAPSULE_FROZEN` / `404` / `409 ERR_CAPSULE_ALREADY_UNSEALED`（既に開封済み）

### 3.6 `POST /capsules/{capsuleId}/unseal` — 開封（不可逆）

任意タイミングでの手動開封（product-spec.md §3.4）。**不可逆操作のため二段階確認を確認トークンで表現**する。押下後、全参加者が即座に開封済み状態に遷移し、全配信先へ配信・通知処理が起動する。

二段階確認フロー（2026-07-03 更新: `confirmation_token` の発行元を §3.5 として明記した二段階フロー）:

1. クライアントは開封確認モーダルを表示する前に `POST /capsules/{capsuleId}/unseal/prepare`（§3.5）を呼び、`confirmation_token` を取得する。
2. クライアントは第2段階モーダルで「開封」と入力させ、`confirmation_text` と、手順1で取得した `confirmation_token` を合わせて本 EP に送信する。
3. サーバーは `confirmation_text == "開封"` を検証（不一致は `400 ERR_UNSEAL_CONFIRMATION_MISMATCH`）。
4. サーバーは `confirmation_token` を検証する（対象カプセル・実行者との一致、TTL 内、未使用であること）。不正・存在しない・使用済みは `400 ERR_CONFIRMATION_TOKEN_INVALID`、TTL（5分）超過は `400 ERR_CONFIRMATION_TOKEN_EXPIRED`。検証成功時は同一トランザクションでトークンを失効させ（単回使用）、二重押下を弾く。

- **パスパラメータ**: `capsuleId`
- **認可**: 対象カプセルの `active` 参加者（全員可）。凍結カプセル（`active` 0 人）は API 経由の手動開封不可（`403 ERR_CAPSULE_FROZEN`。開封日到来の自動開封のみ発火）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `confirmation_text` | string | 必須 | 完全一致 `"開封"` | 第2段階の入力確認 |
| `confirmation_token` | string | 必須 | サーバー発行値（§3.5 で取得） | 冪等・二重押下防止 |

- **レスポンス**: `200`

```json
{
  "capsule_id": "cap_UUID",
  "unsealed_at": "2046-03-14T22:10:00+09:00",
  "unseal_trigger": "manual",
  "unseal_event_id": "uns_UUID",
  "notification_status": "queued"
}
```

- 副作用: `unseal_events` に `trigger_type='manual'`・`executed_by=<自分>` を INSERT（INSERT only）。`capsules.unsealed_at`/`unseal_trigger='manual'` を更新。全配信先への `record_delivery` と全参加者への `unseal_notice` を配信ジョブへ登録（§9）。
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `403 ERR_CAPSULE_FROZEN` / `404` / `409 ERR_CAPSULE_ALREADY_UNSEALED`（既に開封済み） / `400 ERR_UNSEAL_CONFIRMATION_MISMATCH` / `400 ERR_CONFIRMATION_TOKEN_INVALID` / `400 ERR_CONFIRMATION_TOKEN_EXPIRED`

---

## 4. 参加者（members）

`MemberRead` 共通形:

```json
{
  "member_id": "mem_UUID",
  "capsule_id": "cap_UUID",
  "user_id": "usr_UUID",
  "invited_email": "father@example.com",
  "status": "active",
  "display_name": "父",
  "invited_at": "2026-08-01T09:00:00+09:00",
  "joined_at": "2026-08-01T12:00:00+09:00",
  "deleted_at": null
}
```

- `status='deleted'` の場合、`user_id` は返すが `display_name` は「元参加者」に固定（★I。実名は伏せ、`display_name_override` は内部保持）。

### 4.1 `GET /capsules/{capsuleId}/members` — 参加者一覧

- **認可**: 対象カプセルの `active` 参加者。
- **クエリパラメータ**: `status`（任意, `invited` / `active` / `deleted` / `all`。既定 `all`）
- **レスポンス**: `200`（`{ "items": [MemberRead], "total": n }`。削除済みは「元参加者」表記）
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404`

### 4.2 `POST /capsules/{capsuleId}/members` — 招待（メアド）

メールアドレスで参加者を招待する。招待メール（`email_type='invite'`）を送信し、`capsule_members` に `status='invited'` 行を作成する。**参加者上限は両プラン共通で 2 人**（★G。`active` + `invited` の合算で判定）。開封済みカプセルへの新規招待は不可（product-spec.md §5.6）。

- **認可**: 対象カプセルの `active` 参加者（全員可）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `email` | string(email) | 必須 | RFC 5321, max 320 | 招待先。保存時 `LOWER()` 正規化 |

- **重複防止**: `(capsule_id, LOWER(invited_email))` UNIQUE。既存招待/参加と重複時は `409 ERR_MEMBER_ALREADY_INVITED`。
- **招待トークン発行**（2026-07-03 追記）: サーバーは不透明な生トークン（十分なエントロピーを持つランダム文字列）を一度だけ生成する。生トークンは (1) 本エンドポイントのレスポンス `invitation_token` フィールド、(2) 招待メール本文の受諾リンク、の2箇所にのみ含め、それ以降は取得不可能とする。DB には SHA-256 等でハッシュ化した値のみを `capsule_members.invite_token_hash` として保存し、生トークンは保存しない（data-model.md §3.3）。有効期限は `invite_token_expires_at`（data-model.md §3.3）で管理する。
- **レスポンス**: `201`（`MemberRead` + 一度限りの招待トークン）

```json
{
  "member_id": "mem_UUID",
  "capsule_id": "cap_UUID",
  "user_id": null,
  "invited_email": "father@example.com",
  "status": "invited",
  "display_name": null,
  "invited_at": "2026-08-01T09:00:00+09:00",
  "joined_at": null,
  "deleted_at": null,
  "invitation_token": "opaque_invite_token_string"
}
```

- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404` / `409 ERR_MEMBER_LIMIT_REACHED`（上限 2 人） / `409 ERR_MEMBER_ALREADY_INVITED` / `409 ERR_CAPSULE_ALREADY_UNSEALED`（開封後招待不可） / `422`（不正メアド）

### 4.3 `DELETE /capsules/{capsuleId}/members/{memberId}` — 参加者削除 / 退出

対象参加者を削除する（他者削除 or 自己退出）。**削除された参加者の記録は保持・配信される**（社会契約宣言）。`status='deleted'`・`deleted_at`・`deletion_reason`（他者削除 `removed_by_member` / 自己 `self_exit`）・`display_name_override`（表示名スナップショット）を設定。全 `active` 参加者を削除すると凍結状態（product-spec.md §5.6）へ。

- **パスパラメータ**: `capsuleId`, `memberId`
- **認可**: 対象カプセルの `active` 参加者（他者削除・自己退出とも可）。
- **副作用**: 削除された参加者が `added_by` の配信先は `SET NULL`。削除された人自身のメアドが配信先に登録済みなら配信先から除外（product-spec.md §5.3）。
- **レスポンス**: `204 No Content`
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404 ERR_MEMBER_NOT_FOUND` / `409 ERR_MEMBER_ALREADY_DELETED`

### 4.4 `POST /invitations/{token}/accept` — 招待受諾

招待メール内リンクの `token` で招待を受諾し、`active` 参加者になる。**アカウント未登録でも参加可**（product-spec.md §3.3 の参加者状態遷移を参照）だが、当 API 呼び出し時点では Firebase サインイン + `POST /auth/register` 済みであることを前提とする（アプリは招待リンク → サインイン → 本 API の順で処理）。

- **パスパラメータ**: `token`（招待トークン。メール記載の不透明値。生トークンはDBに保存されない。サーバーは受信した `token` を SHA-256 等でハッシュ化し、`capsule_members.invite_token_hash` と突合して照合する — data-model.md §3.3。2026-07-03 追記）
- **認可**: 認証済みユーザー（招待トークンが認可の主体。トークンの `invited_email` とサインイン `email` の一致を検証。不一致は `403 ERR_INVITATION_EMAIL_MISMATCH`）。
- **リクエストボディ**: なし
- **トークン検証**（2026-07-03 追記）: ハッシュ不一致（該当行なし）は `404 ERR_INVITATION_NOT_FOUND`（存在秘匿）。`invite_token_expires_at` を超過した期限切れトークンも同じく `404 ERR_INVITATION_NOT_FOUND` として扱う（無効トークンと失効トークンを区別せず存在秘匿を優先し、招待トークン推測攻撃への情報漏洩を避ける）。
- **副作用**: 対象 `capsule_members` 行を `status='active'`・`user_id=<自分>`・`joined_at=now()` に更新し、`invite_token_hash` / `invite_token_expires_at` を `NULL` にクリアする（data-model.md §3.3）。開封済みカプセルは受諾不可（product-spec.md §5.6）。
- **レスポンス**: `200`（`MemberRead`。`status='active'`）
- **主なエラー**: `401` / `403 ERR_INVITATION_EMAIL_MISMATCH` / `404 ERR_INVITATION_NOT_FOUND`（無効・失効・ハッシュ不一致トークン） / `409 ERR_INVITATION_ALREADY_ACCEPTED` / `409 ERR_CAPSULE_ALREADY_UNSEALED`

---

## 5. 配信先メアド（delivery-addresses）

`DeliveryAddressRead` 共通形:

```json
{
  "id": "dad_UUID",
  "capsule_id": "cap_UUID",
  "email": "daughter@example.com",
  "tag": "all",
  "label": "娘のメアド",
  "is_active": true,
  "added_by": "usr_UUID",
  "bounce_count": 0,
  "paused_reason": null,
  "created_at": "2026-07-02T10:10:00+09:00",
  "updated_at": "2026-07-02T10:10:00+09:00"
}
```

- `tag`: `all`（全員）/ `parents_only`（内輪のみ）。UI 表記は「全員 / 内輪のみ」（★K）。`all` = 「全員に届ける」記録のみ、`parents_only` = 「全員」+「内輪のみ」記録が届く（product-spec.md §5.1・§5.2・data-model §4.5）。

### 5.1 `GET /capsules/{capsuleId}/delivery-addresses` — 配信先一覧

- **認可**: 対象カプセルの `active` 参加者。
- **レスポンス**: `200`（`{ "items": [DeliveryAddressRead], "total": n }`）。`parents_only` 記録が届くタグ（`parents_only`）のメアドが 0 件のとき、クライアントは警告バナー表示（product-spec.md §5.2）。
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404`

### 5.2 `POST /capsules/{capsuleId}/delivery-addresses` — 配信先追加

配信先メアドを追加する。**上限は両プラン共通 5 個**（★G）。`email` は `LOWER()` 正規化し `(capsule_id, LOWER(email))` UNIQUE で重複防止。`tag` は必須（既定 `all`。無タグ状態は不可・product-spec.md §5.2）。

- **認可**: 対象カプセルの `active` 参加者。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `email` | string(email) | 必須 | RFC 5321, max 254 | 保存時 `LOWER()` 正規化 |
| `tag` | string | 任意 | `all` / `parents_only`（既定 `all`） | 配信フィルタ |
| `label` | string \| null | 任意 | max 100 | 表示名（例「娘のメアド」） |

- **レスポンス**: `201`（`DeliveryAddressRead`）
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404` / `409 ERR_DELIVERY_ADDRESS_LIMIT_REACHED`（上限 5） / `409 ERR_DELIVERY_ADDRESS_DUPLICATE`（LOWER 重複） / `422`（不正メアド・不正 tag）

### 5.3 `PATCH /capsules/{capsuleId}/delivery-addresses/{addressId}` — 配信先更新

`tag` / `label` / `is_active` を更新する。バウンスで一時停止された配信先の再有効化にも使う（`is_active=true` で `paused_reason` をクリア）。`email` は変更不可（変更したい場合は削除 → 再追加）。

- **パスパラメータ**: `capsuleId`, `addressId`
- **認可**: 対象カプセルの `active` 参加者（全員可。追加者本人に限定しない）。
- **リクエストボディ**（すべて任意・指定項目のみ）:

| 項目 | 型 | バリデーション |
|---|---|---|
| `tag` | string | `all` / `parents_only` |
| `label` | string \| null | max 100 |
| `is_active` | boolean | — |

- **レスポンス**: `200`（更新後 `DeliveryAddressRead`）
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404 ERR_DELIVERY_ADDRESS_NOT_FOUND` / `422`

### 5.4 `DELETE /capsules/{capsuleId}/delivery-addresses/{addressId}` — 配信先削除

- **認可**: 対象カプセルの `active` 参加者。
- **レスポンス**: `204 No Content`
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404 ERR_DELIVERY_ADDRESS_NOT_FOUND`

> 注: 開封済みカプセルでも配信先の追加・変更・削除は可能（product-spec.md §5.6。追加分への再送信は別途手動運用）。

---

## 6. 記録（records）

記録は **INSERT only**（保存後は編集・削除不可。全ステータスで削除禁止・product-spec.md §3.2）。1 週間ウィンドウ（`window_ends_at`。投稿翌日 0 時 JST 起算 +7 日、生成列）と `visibility` により封印モードの他参加者表示を制御する。

`RecordRead`（表示レベルにより項目が変わる。§6.2）:

```json
{
  "id": "rec_UUID",
  "capsule_id": "cap_UUID",
  "author_id": "usr_UUID",
  "author_display_name": "母",
  "body": "娘が初めて笑った日のこと……",
  "visibility": "all",
  "posted_at": "2026-07-02T21:00:00+09:00",
  "window_ends_at": "2026-07-10T00:00:00+09:00",
  "is_sealed_for_viewer": false,
  "attachments": [],
  "created_at": "2026-07-02T21:00:00+09:00"
}
```

### 6.1 `POST /capsules/{capsuleId}/records` — 記録作成

記録を投稿する。本文最大 5,000 字。`visibility` で届け先トグル（全員 / 内輪のみ）を指定。**月次記録上限のソフトブロック**を適用する（下記）。

- **認可**: 対象カプセルの `active` 参加者。開封済みカプセルは「読む期間」のため投稿不可（`409 ERR_CAPSULE_ALREADY_UNSEALED`）。凍結カプセルも投稿不可（`403 ERR_CAPSULE_FROZEN`）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `body` | string | 必須 | 1–5000 字（`char_length`） | 本文。空/超過は `422` |
| `visibility` | string | 任意 | `all` / `parents_only`（既定 `all`） | 届け先トグル |

- `posted_at` / `window_ends_at` はサーバー/DB が確定（クライアント指定不可。`window_ends_at` は生成列）。

- **月次上限（ソフトブロック）**: 月次件数は投稿者（`author_id`）× JST 暦月で集計する。
  - **無料プラン**: 月 5 件。5 件到達後の 6 件目は **`402 ERR_MONTHLY_QUOTA_EXCEEDED`**（記録は保存されない。AC-02）。レスポンスに課金誘導メタを含める（§7.1）。
  - **有料プラン**: 月 200 件。200 件到達後の 201 件目は **`409 ERR_MONTHLY_LIMIT_REACHED`**（“来月リセット”。AC-13）。
  - いずれも上限手前で警告（無料は 5 件目、有料は 180 件目付近）をクライアントが表示するため、`GET /billing/subscription` またはレスポンスの `usage` メタを参照する。

- **レスポンス**: `201`（`RecordRead`。自分の記録なので `body` 全文を含む）
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `403 ERR_CAPSULE_FROZEN` / `404` / `409 ERR_CAPSULE_ALREADY_UNSEALED` / `409 ERR_MONTHLY_LIMIT_REACHED` / `402 ERR_MONTHLY_QUOTA_EXCEEDED` / `422`（本文長）

`402` レスポンス例（ソフトブロック。§7.1 と整合）:

```json
{
  "detail": "今月の無料枠（5/5件）を使いきりました",
  "code": "ERR_MONTHLY_QUOTA_EXCEEDED",
  "meta": {
    "used": 5,
    "limit": 5,
    "period": "2026-07",
    "resets_at": "2026-08-01T00:00:00+09:00",
    "upgrade": {
      "monthly_product_id_apple": "com.lydear.oyagokoro.premium.monthly",
      "monthly_product_id_google": "premium_monthly",
      "trial_days": 7
    }
  }
}
```

### 6.2 `GET /capsules/{capsuleId}/records` — 記録一覧（封印モード表示ルール）

封印モードアーカイブ（product-spec.md §4.1）の主データ。**表示レベルは閲覧者との関係で決まる**（product-spec.md §3.2・data-model §5.1）:

| 記録の種別 | 返却内容 |
|---|---|
| 自分が書いた記録 | 常時全文（`body`・`attachments` を返す。`is_sealed_for_viewer=false`） |
| 他参加者・ウィンドウ中（`window_ends_at > now`） | 全文（`body`・`attachments` を返す）+ ウィンドウ残り情報 |
| 他参加者・封印中（`window_ends_at <= now` かつ未開封） | **メタのみ**（`body`・`attachments` は返さず `null`。`is_sealed_for_viewer=true`。投稿者・投稿日・件数カウント用の最小情報のみ） |
| 開封済みカプセル（`unsealed_at` 非 NULL） | 全記録を全文（product-spec.md §4.1「開封後フルアーカイブ」。削除済み参加者分も「元参加者」表記で全文） |

- **認可**: 対象カプセルの `active` 参加者。
- **クエリパラメータ**: `author_id`（任意フィルタ）/ `visibility`（任意）/ `year_month`（任意 `YYYY-MM`、開封後フィルタ用）/ `limit`（既定 50, max 100）/ `cursor`（`posted_at DESC` ページング）
- **レスポンス**: `200`

```json
{
  "items": [
    {
      "id": "rec_a", "author_id": "self_UUID", "author_display_name": "母",
      "body": "自分の記録は常時全文", "visibility": "all",
      "posted_at": "2026-07-02T21:00:00+09:00",
      "window_ends_at": "2026-07-10T00:00:00+09:00",
      "is_sealed_for_viewer": false, "attachments": []
    },
    {
      "id": "rec_b", "author_id": "partner_UUID", "author_display_name": "父",
      "body": null, "visibility": null,
      "posted_at": "2026-06-20T08:00:00+09:00",
      "window_ends_at": "2026-06-28T00:00:00+09:00",
      "is_sealed_for_viewer": true, "attachments": null
    }
  ],
  "counts": { "self": 5, "by_member": { "partner_UUID": 8 } },
  "next_cursor": null
}
```

- 封印中の他者記録は `body=null`・`visibility=null`・`attachments=null`（内容を漏らさない）。ただし件数（`counts`）は封印中でも可視（★L・product-spec.md §4.2「件数常時可視」）。
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404`

### 6.3 `GET /records/{recordId}` — 記録単体取得

- **パスパラメータ**: `recordId`
- **認可**: その記録が属するカプセルの `active` 参加者。表示レベルは §6.2 と同一ルール（封印中の他者記録はメタのみ、`403` ではなく `is_sealed_for_viewer=true` の部分表現で返す）。非参加者は `404 ERR_RECORD_NOT_FOUND`。
- **レスポンス**: `200`（`RecordRead`）
- **主なエラー**: `401` / `404 ERR_RECORD_NOT_FOUND`

### 6.4 `POST /capsules/{capsuleId}/export` — エクスポート生成（PDF / JSON / Markdown・非同期）

カプセルの記録をエクスポートする。**全プラン無料**（データ完全エクスポート権・product-spec.md §2 社会契約宣言 / product-spec.md §4.1 MVP 機能）。1,000 レコード規模でも 5 分以内に生成する要件（product-spec.md §8.4 / AC-11）のため、**非同期ジョブとして受理**し `202` を返す。生成物は S3 に置き、`§6.5` のジョブ取得で presigned GET URL を得る。

- **パスパラメータ**: `capsuleId`
- **認可**: 対象カプセルの `active` 参加者。非参加者は `404 ERR_CAPSULE_NOT_FOUND`。
- **エクスポート範囲（封印状態と可視性の整合。§6.2・product-spec.md §4.1）**:

| カプセル状態 | 含まれる記録 |
|---|---|
| 封印中（`unsealed_at IS NULL`） | **自分が書いた記録のみ**（他参加者の記録は封印/ウィンドウ状態に関わらず含めない。内容漏洩を防ぐ） |
| 開封済み（`unsealed_at` 非 NULL） | **全記録**（全参加者・全期間。削除済み参加者分は「元参加者」表記で含む。product-spec.md §4.1「開封後フルアーカイブ」と同一） |

- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `formats` | string[] | 任意 | 各要素 `pdf` / `json` / `markdown`（既定 3 形式すべて） | 生成する形式。未指定時は 3 形式生成 |

- **レスポンス**: `202 Accepted`（生成ジョブを受理。ポーリング先は `§6.5`）

```json
{
  "export_job_id": "exp_UUID",
  "capsule_id": "cap_UUID",
  "status": "queued",
  "formats": ["pdf", "json", "markdown"],
  "scope": "sealed_self_only",
  "requested_at": "2026-07-02T22:00:00+09:00"
}
```

- `scope` は `sealed_self_only`（封印中・自分の記録のみ）/ `unsealed_all`（開封後・全記録）。生成物とジョブは要求者本人に紐付き、封印中エクスポートは本人以外に開示しない。
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404 ERR_CAPSULE_NOT_FOUND` / `422`（未対応 format 指定 → `ERR_EXPORT_FORMAT_INVALID`）
- ジョブ状態は `export_jobs` テーブル（data-model.md §3.12）に永続化される。サーバー/ワーカーの再起動をまたいでもジョブは失われない。レスポンスの `export_job_id` は `export_jobs.id` に対応する（2026-07-03 追記）。

### 6.5 `GET /capsules/{capsuleId}/export/{jobId}` — エクスポート結果取得（ジョブ状態 / ダウンロード URL）

`§6.4` で受理したエクスポートジョブの状態と、完了時のダウンロード URL を取得する。クライアントは `status` が `completed` になるまでポーリングする。

- **パスパラメータ**: `capsuleId`, `jobId`
- **認可**: 対象カプセルの `active` 参加者、かつ**当該ジョブの要求者本人**（封印中エクスポートは自分の記録を含むため、他参加者には開示しない）。要求者以外・非参加者は `404 ERR_EXPORT_JOB_NOT_FOUND`。
- **レスポンス**: `200`

```json
{
  "export_job_id": "exp_UUID",
  "capsule_id": "cap_UUID",
  "status": "completed",
  "formats": ["pdf", "json", "markdown"],
  "scope": "unsealed_all",
  "download_urls": {
    "pdf": "https://oyagokoro-export-prod.s3.ap-northeast-1.amazonaws.com/...&X-Amz-Signature=...",
    "json": "https://oyagokoro-export-prod.s3.ap-northeast-1.amazonaws.com/...&X-Amz-Signature=...",
    "markdown": "https://oyagokoro-export-prod.s3.ap-northeast-1.amazonaws.com/...&X-Amz-Signature=..."
  },
  "expires_at": "2026-07-02T23:05:00+09:00",
  "completed_at": "2026-07-02T22:03:00+09:00"
}
```

- `status`: `queued` / `processing` / `completed` / `failed`。`completed` 以外では `download_urls` は `null`。`failed` 時は `error_message` を含める（再実行は `§6.4` を再度呼ぶ）。
- `download_urls` の各 URL は短命の S3 presigned GET（`expires_at` まで）。PDF は PDF/A-1b 準拠（product-spec.md §8.1）。
- 本エンドポイントが返す `status` / `error_message` / `expires_at` は `export_jobs`（data-model.md §3.12）の同名カラムにそのまま対応する。`download_urls` は `export_jobs.object_keys`（S3 オブジェクトキー）から presigned GET を都度発行して返す（2026-07-03 追記）。
- **主なエラー**: `401` / `403 ERR_NOT_CAPSULE_MEMBER` / `404 ERR_EXPORT_JOB_NOT_FOUND`

> エクスポートジョブ状態は非同期ワーカー（§9.2 の内部ジョブと同系。起動トリガーは Vercel Cron → `POST /internal/jobs/*`）で処理し、`export_jobs` テーブル（data-model.md §3.12）に永続化する（新設決定・2026-07-03）。ジョブ管理用ストア（生成物 S3 キー・要求者・scope・有効期限）はこのテーブルで一元管理し、サーバー/ワーカーの再起動をまたいでもジョブ状態は失われない。

---

## 7. 課金（IAP: Apple / Google）

**課金は Apple App Store / Google Play の In-App Purchase に確定**。バックエンドは決済そのものを扱わず、**クライアント申告を信用せず**にストアのサーバー API でレシート/購入トークンを検証してエンタイトルメントを確定する。購読状態の真実の源はストア側、当方 DB はミラー（IAP 決定メモ §0）。

商品 ID（owner-setup-guide §2.4）:

| 商品 | Apple `product_id` | Google `product_id` | 種別 |
|---|---|---|---|
| 月額プラン | `com.lydear.oyagokoro.premium.monthly` | `premium_monthly` | 自動更新サブスク |
| 年額プラン | `com.lydear.oyagokoro.premium.yearly` | `premium_yearly` | 自動更新サブスク |
| 追加ストレージ 10GB | `com.lydear.oyagokoro.storage.10gb` | `storage_10gb` | 消費型 |

**user 紐付け規約**（IAP 決定メモ §1・§7）: 購入時にアプリは `users.id`（UUID）を Apple `appAccountToken` / Google `obfuscatedExternalAccountId` に設定する。専用カラムは持たず、検証時に取得した購読識別子 → `user_id` の DB 逆引きを権威とする。

### 7.1 `POST /billing/iap/verify` — サブスク購入検証 / 登録

アプリが購入完了後に呼ぶ。プラットフォームのレシート/購入トークンをサーバー検証し、`subscriptions` を UPSERT、エンタイトルメントを確定して `users.current_plan` を同一トランザクションで同期する。

- **認可**: 認証済みユーザー本人（`users.id` = 紐付け先）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `platform` | string | 必須 | `apple` / `google` | ストア種別 |
| `product_id` | string | 必須 | 既知の商品 ID | 購入商品 |
| `transaction_id` | string | 条件付き | Apple 時必須 | Apple の transactionId（`originalTransactionId` 導出用） |
| `purchase_token` | string | 条件付き | Google 時必須 | Google の purchaseToken |
| `environment` | string | 任意 | `sandbox` / `production` | 省略時サーバー判定 |

- `platform=apple` は `transaction_id` 必須、`google` は `purchase_token` 必須（不足は `422`）。
- **サーバー検証**:
  - Apple: 署名付き transaction（JWS）を x5c チェーンで Apple Root CA まで検証、必要に応じ App Store Server API で再取得。`originalTransactionId` を購読不変キーとする。
  - Google: `purchases.subscriptionsv2.get(purchaseToken)` で `subscriptionState` を取得（通知本文でなく検証 API で状態確定）。
  - 検証失敗（署名不正・未購入・商品不一致）は `400 ERR_IAP_VERIFICATION_FAILED`。
- **冪等 / 競合**: `subscriptions.user_id` UNIQUE + プラットフォーム別識別子 UNIQUE（`original_transaction_id` / `purchase_token`）で UPSERT。**別 user が同一識別子を主張**（family 共有・中古端末等）した場合は識別子 UNIQUE 側を正として既存行を維持し `409 ERR_IAP_IDENTIFIER_CONFLICT`（ログ + サポート対応。IAP 決定メモ §7）。sandbox 購入は本番エンタイトルメントを付与しない（`environment` ガード）。
- **レスポンス**: `200`（`SubscriptionRead`。§7.2 と同形）
- **主なエラー**: `401` / `400 ERR_IAP_VERIFICATION_FAILED` / `409 ERR_IAP_IDENTIFIER_CONFLICT` / `422`（platform と識別子の不整合）

### 7.2 `GET /billing/subscription` — 購読状態取得

現在の購読状態と利用枠を返す。真実の源は `subscriptions`。

- **認可**: 認証済みユーザー本人。
- **レスポンス**: `200`（`SubscriptionRead`）。無料ユーザーは `plan_type='free'`・`status` 相当を `free` として返す。

```json
{
  "plan_type": "paid_monthly",
  "status": "active",
  "platform": "apple",
  "product_id": "com.lydear.oyagokoro.premium.monthly",
  "auto_renew": true,
  "current_period_end": "2026-08-02T10:00:00+09:00",
  "trial_end": null,
  "cancel_at": null,
  "environment": "production",
  "entitlement": {
    "is_premium": true,
    "monthly_record_limit": 200,
    "attachments_enabled": true
  },
  "usage": {
    "records_this_month": 12,
    "period": "2026-07",
    "storage_used_bytes": 524288000,
    "storage_quota_bytes": 5368709120
  }
}
```

- `status` は `trialing` / `active` / `in_grace_period` / `canceled` / `on_hold` / `expired`（IAP 決定メモ §2.3）。`entitlement.is_premium` は `status IN ('trialing','active','in_grace_period')` または（`canceled` かつ `current_period_end > now`）で `true`。`on_hold` / `expired` は `false`。
- `storage_quota_bytes` は基本 5GB（有料付帯）+ 有効な追加購入（`SUM(gb_added) WHERE revoked_at IS NULL AND expires_at > now`）。
- **主なエラー**: `401` / `404 ERR_USER_NOT_FOUND`

### 7.3 `POST /billing/iap/storage` — 追加ストレージ購入検証（消費型・冪等）

追加ストレージ 10GB（買い切り 1,500 円・20 年保管込み）の消費型 IAP を検証・記録する。

- **認可**: 認証済みユーザー本人。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `platform` | string | 必須 | `apple` / `google` | ストア種別 |
| `product_id` | string | 必須 | ストレージ商品 ID | `...storage.10gb` / `storage_10gb` |
| `transaction_id` | string | 条件付き | Apple 時必須 | 消費型 transactionId |
| `purchase_token` | string | 条件付き | Google 時必須 | 消費型 purchaseToken |
| `environment` | string | 任意 | `sandbox` / `production` | — |

- **サーバー検証 / 冪等**:
  - Apple: JWS 署名検証 → `type=Consumable`・`productId` 一致を確認。
  - Google: `purchases.products.get` で `purchaseState==0`（purchased）確認 → `acknowledge` → `consume`（再購入可能化）。
  - 記録は `storage_purchases` に `INSERT ... ON CONFLICT (platform, provider_transaction_id) DO NOTHING`。`provider_transaction_id` は Apple `transactionId` / Google `purchaseToken`。**INSERT が実際に行われた時のみストレージ加算**（二重付与を DB で完全排除）。`price_jpy` はサーバー側の商品→価格マップ（1,500 円）で記録。
- **レスポンス**: `201`（新規付与時）/ `200`（冪等再送で既存反映）

```json
{
  "storage_purchase_id": "stp_UUID",
  "gb_added": 10,
  "price_jpy": 1500,
  "purchased_at": "2026-07-02T11:00:00+09:00",
  "expires_at": "2046-07-02T11:00:00+09:00",
  "storage_quota_bytes": 16106127360
}
```

- **主なエラー**: `401` / `400 ERR_IAP_VERIFICATION_FAILED` / `422`（platform と識別子の不整合）

### 7.4 `POST /webhooks/apple/notifications` — Apple ASSN V2（署名 JWS）

App Store Server Notifications V2 の受信口。サブスク更新・解約・返金等が Apple から届く。

- **認可**: 不要（Firebase 認証対象外）。**Apple 署名（JWS x5c チェーンを Apple Root CA まで）で検証**。失敗は `400 ERR_WEBHOOK_SIGNATURE_INVALID`。
- **リクエストボディ**: `{ "signedPayload": "<JWS>" }`
- **処理**（IAP 決定メモ §4.1）:
  1. 署名検証 → デコードで `notificationType` + `subtype` + `data.signedTransactionInfo` + `signedRenewalInfo` + `environment` を取得。
  2. `original_transaction_id` で `subscriptions` 逆引き（無ければ `appAccountToken=users.id` で user 特定し新規行）。
  3. §2.3 マッピングで `status` 導出、`current_period_end`（`expiresDate`）/ `auto_renew` / `latest_notification_type` / `latest_notification_at`（`signedDate`）を更新。
  4. **`latest_notification_at` 単調ガード**: 保存済みより古い通知は破棄（順序逆転で状態を巻き戻さない）。
  5. 同一トランザクションで `users.current_plan` 再計算（エンタイトルメント無なら `free`）。返金（`REFUND`）は `status='expired'` + `current_plan='free'`（行は監査保持）。
- **レスポンス**: `200`（正常受理。Apple は 2xx を成功とみなす）
- **主なエラー**: `400 ERR_WEBHOOK_SIGNATURE_INVALID` / `400 ERR_WEBHOOK_PAYLOAD_INVALID`（500 は Apple がリトライするため、恒久エラーは 2xx/4xx で握る運用）

### 7.5 `POST /webhooks/google/rtdn` — Google RTDN（Pub/Sub push）

Real-time Developer Notifications を Pub/Sub push で受信する。**通知本文は購読状態を含まない**ため、必ず検証 API を叩いて状態を取り直す（IAP 決定メモ §0-2・§4.2）。

- **認可**: 不要。Pub/Sub push の OIDC トークン（`Authorization: Bearer <Google 署名 JWT>`）を検証。失敗は `400 ERR_WEBHOOK_SIGNATURE_INVALID`。
- **リクエストボディ**: Pub/Sub push 形式 `{ "message": { "data": "<base64>", "messageId": "..." }, "subscription": "..." }`
- **処理**:
  1. `message.data` を base64 デコード → `subscriptionNotification`（`purchaseToken` / `subscriptionId` / `notificationType`）/ `voidedPurchaseNotification` / `oneTimeProductNotification` を判別。
  2. **通知本文で状態を決めない。** サブスクは `purchases.subscriptionsv2.get(purchaseToken)`、消費型は `purchases.products.get` で権威状態を取得。
  3. `purchase_token` で逆引き。ローテーション時は `linkedPurchaseToken` 連鎖 + `obfuscatedExternalAccountId=users.id` で同一 user 行を特定し **`purchase_token` を最新値に UPDATE**（トークンローテーション追跡）。
  4. §2.3 マッピングで `status` 導出 → 単調ガード → `users.current_plan` 同期。`voidedPurchaseNotification`（サブスク）は `status='expired'`、消費型ストレージの返金は `storage_purchases.revoked_at` を設定し有効量から除外。
- **レスポンス**: `200`（ack。非 2xx は Pub/Sub が再送）
- **主なエラー**: `400 ERR_WEBHOOK_SIGNATURE_INVALID` / `400 ERR_WEBHOOK_PAYLOAD_INVALID`

---

## 8. 添付ファイル（MVP+: 画像 / 音声）

有料プランのみ（写真 5 枚/記録・音声 3 分/記録）。実体は **S3 presigned URL で直アップロード**し、DB にはメタデータのみ保存する。ストレージ消費（実バイト数）を `storage_usage`（capsule 単位・即時更新）に計上する。

フロー: (1) presign 発行 → (2) クライアントが S3 へ直 PUT → (3) 完了通知でメタ確定・DB 登録・使用量計上。

### 8.1 `POST /records/{recordId}/attachments` — presigned URL 発行

添付アップロード用の S3 presigned PUT URL を発行する。この時点でストレージ上限・プラン・枚数を事前チェックする。

- **パスパラメータ**: `recordId`
- **認可**: 記録の投稿者本人（`author_id` = 自分）かつ有料プラン。無料プランは `402 ERR_ATTACHMENT_REQUIRES_PAID`。開封済みカプセルの記録には添付不可（`409`）。
- **リクエストボディ**:

| 項目 | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `attachment_type` | string | 必須 | `image` / `audio` | 添付種別 |
| `mime_type` | string | 必須 | 許可 MIME | `image/webp` `image/jpeg` / `audio/mpeg` `audio/aac` |
| `byte_size` | integer | 必須 | `> 0`・上限内 | 予定バイト数（上限・枚数事前チェック用） |
| `duration_seconds` | integer | 条件付き | audio 時必須・≤180 | 音声長（3 分上限） |
| `width` / `height` | integer | 条件付き | image 時必須 | 画像寸法 |

- **上限チェック**: 画像は 1 記録 5 枚まで（`409 ERR_ATTACHMENT_COUNT_EXCEEDED`）。`storage_usage.used_bytes + byte_size` がプラン枠（5GB + 有効追加購入）を超える場合 `409 ERR_STORAGE_LIMIT_EXCEEDED`（購入誘導メタ付き）。
- **レスポンス**: `201`

```json
{
  "attachment_id": "att_UUID",
  "upload_url": "https://oyagokoro-media-prod.s3.ap-northeast-1.amazonaws.com/...&X-Amz-Signature=...",
  "s3_object_key": "attachments/cap_UUID/rec_UUID/att_UUID.webp",
  "expires_in": 900,
  "required_headers": { "Content-Type": "image/webp" }
}
```

- `att_UUID` は `pending` 状態のプレースホルダ（`byte_size` 確定は完了通知時）。presign は 15 分有効。
- **主なエラー**: `401` / `403 ERR_NOT_RECORD_AUTHOR` / `402 ERR_ATTACHMENT_REQUIRES_PAID` / `404 ERR_RECORD_NOT_FOUND` / `409 ERR_CAPSULE_ALREADY_UNSEALED` / `409 ERR_ATTACHMENT_COUNT_EXCEEDED` / `409 ERR_STORAGE_LIMIT_EXCEEDED` / `422`

### 8.2 `POST /records/{recordId}/attachments/{attachmentId}/complete` — アップロード完了通知

S3 直 PUT 完了後に呼ぶ。サーバーは S3 の実オブジェクト（存在・実バイト数・Content-Type）を検証し、`record_attachments` を確定登録する。INSERT トリガーで `storage_usage` が即時更新される。

- **パスパラメータ**: `recordId`, `attachmentId`
- **認可**: 記録の投稿者本人。
- **リクエストボディ**: なし（サーバーが S3 HeadObject で実測。クライアント申告値は検証で上書き）
- **副作用**: `record_attachments` を INSERT（`byte_size` は実測値）。`storage_usage.used_bytes` 即時加算。実オブジェクトが存在しない/申告と乖離が大きい場合は `409 ERR_ATTACHMENT_NOT_UPLOADED`。
- **レスポンス**: `201`（`AttachmentRead`）

```json
{
  "id": "att_UUID",
  "record_id": "rec_UUID",
  "attachment_type": "image",
  "s3_object_key": "attachments/cap_UUID/rec_UUID/att_UUID.webp",
  "mime_type": "image/webp",
  "byte_size": 512000,
  "width": 1920,
  "height": 1280,
  "created_at": "2026-07-02T21:05:00+09:00"
}
```

- **主なエラー**: `401` / `403 ERR_NOT_RECORD_AUTHOR` / `404 ERR_ATTACHMENT_NOT_FOUND` / `409 ERR_ATTACHMENT_NOT_UPLOADED` / `409 ERR_STORAGE_LIMIT_EXCEEDED`（実測超過）

> 添付の閲覧: `GET /records/{id}`・`GET /capsules/{id}/records` のレスポンス `attachments[]` に S3 presigned GET URL（短命）を含めて返す。封印中の他者記録では `attachments=null`（§6.2）。

---

## 9. 主要フローの補足

### 9.1 開封 → 配信の可視性フィルタ（visibility × tag）

開封イベント（手動 `POST /unseal` または開封日自動）を起点に、`records` を全配信先へ配信する。可視性フィルタは以下（data-model §4.5・product-spec.md §5.1・§5.2・AC-08）:

| 記録 `visibility` | 配信先 `tag='all'` | 配信先 `tag='parents_only'` |
|---|---|---|
| `all`（全員に届ける） | 配信する | 配信する |
| `parents_only`（内輪のみ） | **配信しない** | 配信する |

- スキップした配信も `email_deliveries` に `status='skipped'`・`skipped_reason='no_matching_tag'` として記録し、配信意志の証跡を残す（§0.2）。
- 全配信先が `all` タグのみで `parents_only` 記録がある場合、その記録は送信先 0 件（`skipped`、プライバシー保護優先。AC-16 / product-spec.md §5.2）。
- 削除済み参加者（`status='deleted'`）の記録も配信対象に含む（AC-10）。配信メール内では「家族の一員より」等で匿名化（product-spec.md §5.3）。

### 9.2 開封日到来バッチ / 配信（内部ジョブ・外部 API ではない）

以下は外部公開エンドポイントではなく、スケジューラ（Vercel Cron 等）から起動する内部ジョブとして実装する。API 仕様のスコープ外だが、整合のため概説する。

- **開封日到来検知ジョブ**: JST 0 時に `capsules WHERE unsealed_at IS NULL AND open_at <= now()` をポーリング。該当カプセルを `unseal_trigger='scheduled'` で開封（`unseal_events` に `trigger_type='scheduled'`・`executed_by=NULL` を INSERT）→ 配信ジョブ起動（AC-07）。1 週間ウィンドウ中の記録も含め全記録が即開封（product-spec.md §3.5）。
- **配信ジョブ**: 開封イベントごとに §9.1 フィルタで `email_deliveries` を生成し、メール送信（`record_delivery` / `unseal_notice`）。
- **バウンス処理**: 配信失敗（バウンス）を検知したら 24 時間以内に最大 2 回リトライ（`attempt_count` 1–3）。失敗継続で `delivery_addresses.is_active=false`・`paused_reason='bounce'`・`bounce_count++`・`last_bounced_at` 更新。追加者（参加者）へ `bounce_warning` 通知。無効メアドは次回配信から除外（手動再有効化まで。product-spec.md §5.6）。
- **トライアル終了バッチ**: `subscriptions.trial_end` 到来を検知（時計はストア管理のため状態確定は通知/検証 API 経由）。

### 9.3 ソフトブロックの返却形（再掲）

- 無料枠（月 5 件）超過: `402 ERR_MONTHLY_QUOTA_EXCEEDED` + `meta`（`used`/`limit`/`resets_at`/`upgrade`。§6.1）。クライアントは product-spec.md §5.5 のソフトブロック UI（7 日間無料トライアル / 来月まで待つ）を表示。
- 有料枠（月 200 件）超過: `409 ERR_MONTHLY_LIMIT_REACHED`（“来月リセット”モーダル。AC-13）。
- ストレージ枠超過: `409 ERR_STORAGE_LIMIT_EXCEEDED` + 追加購入誘導（10GB / 1,500 円。§8）。

---

## 10. エラーコード一覧（ERR_xxx）

| コード | HTTP | 発生条件 |
|---|---|---|
| `ERR_UNAUTHENTICATED` | 401 | ID Token 不正・期限切れ・欠落 |
| `ERR_INVALID_TOKEN` | 400 | トークンに email が無い等、必須クレーム欠落 |
| `ERR_USER_NOT_FOUND` | 404 | `register` 未実行でユーザー行が無い |
| `ERR_TERMS_NOT_AGREED` | 403 | 規約未同意でカプセル作成等の要同意操作 |
| `ERR_CAPSULE_NOT_FOUND` | 404 | カプセル未存在 or 非参加者への存在秘匿 |
| `ERR_NOT_CAPSULE_MEMBER` | 403 | 対象カプセルの `active` 参加者でない |
| `ERR_CAPSULE_ALREADY_UNSEALED` | 409 | 開封済みカプセルへの投稿・招待・開封日変更・再開封 |
| `ERR_CAPSULE_FROZEN` | 403 | 凍結カプセル（`active` 0 人）への手動開封・投稿 |
| `ERR_OPEN_AT_IN_PAST` | 422 | 開封日に過去日時を指定 |
| `ERR_UNSEAL_CONFIRMATION_MISMATCH` | 400 | 開封の確認文字列（「開封」）不一致 |
| `ERR_CONFIRMATION_TOKEN_INVALID` | 400 | `confirmation_token` が不正・存在しない・使用済み（§3.5/§3.6。2026-07-03 追記） |
| `ERR_CONFIRMATION_TOKEN_EXPIRED` | 400 | `confirmation_token` の有効期限（TTL 5 分）切れ（§3.5/§3.6。2026-07-03 追記） |
| `ERR_MEMBER_NOT_FOUND` | 404 | 参加者レコード未存在 |
| `ERR_MEMBER_LIMIT_REACHED` | 409 | 参加者上限 2 人超過（★G） |
| `ERR_MEMBER_ALREADY_INVITED` | 409 | 同一メアドで既に招待/参加済み（LOWER 重複） |
| `ERR_MEMBER_ALREADY_DELETED` | 409 | 既に削除済みの参加者を再削除 |
| `ERR_INVITATION_NOT_FOUND` | 404 | 招待トークンが無効・失効 |
| `ERR_INVITATION_EMAIL_MISMATCH` | 403 | 招待メアドとサインイン email 不一致 |
| `ERR_INVITATION_ALREADY_ACCEPTED` | 409 | 受諾済み招待の再受諾 |
| `ERR_DELIVERY_ADDRESS_NOT_FOUND` | 404 | 配信先未存在 |
| `ERR_DELIVERY_ADDRESS_LIMIT_REACHED` | 409 | 配信先上限 5 個超過（★G） |
| `ERR_DELIVERY_ADDRESS_DUPLICATE` | 409 | 同一カプセル内メアド重複（LOWER 正規化） |
| `ERR_RECORD_NOT_FOUND` | 404 | 記録未存在 or 非参加者への存在秘匿 |
| `ERR_MONTHLY_QUOTA_EXCEEDED` | 402 | 無料枠 月 5 件超過（ソフトブロック・課金誘導） |
| `ERR_MONTHLY_LIMIT_REACHED` | 409 | 有料枠 月 200 件超過（来月リセット） |
| `ERR_ATTACHMENT_REQUIRES_PAID` | 402 | 無料プランで添付を試行 |
| `ERR_NOT_RECORD_AUTHOR` | 403 | 記録投稿者本人でない者の添付操作 |
| `ERR_ATTACHMENT_NOT_FOUND` | 404 | 添付レコード未存在 |
| `ERR_ATTACHMENT_COUNT_EXCEEDED` | 409 | 画像 5 枚/記録 超過 |
| `ERR_ATTACHMENT_NOT_UPLOADED` | 409 | S3 に実体が無い/申告と乖離した完了通知 |
| `ERR_STORAGE_LIMIT_EXCEEDED` | 409 | ストレージ枠超過（追加購入誘導） |
| `ERR_EXPORT_FORMAT_INVALID` | 422 | エクスポートで未対応 format を指定（`pdf`/`json`/`markdown` 以外） |
| `ERR_EXPORT_JOB_NOT_FOUND` | 404 | エクスポートジョブ未存在 or 要求者本人でない者への存在秘匿 |
| `ERR_IAP_VERIFICATION_FAILED` | 400 | ストア署名/購入検証に失敗（署名不正・未購入・商品不一致） |
| `ERR_IAP_IDENTIFIER_CONFLICT` | 409 | 別 user が同一購読識別子を主張（family 共有・中古端末等） |
| `ERR_WEBHOOK_SIGNATURE_INVALID` | 400 | Apple JWS / Google OIDC 署名検証失敗 |
| `ERR_WEBHOOK_PAYLOAD_INVALID` | 400 | Webhook 本文のデコード/形式不正 |

---

## 11. 付録: リソース × エンドポイント一覧

| # | リソース | メソッド + パス | 概要 |
|---|---|---|---|
| 1 | 認証/ユーザー | POST `/auth/register` | 初回同期（冪等 UPSERT） |
| 2 | 認証/ユーザー | GET `/users/me` | 自分の情報取得 |
| 3 | 認証/ユーザー | PATCH `/users/me` | プロフィール更新 |
| 4 | 認証/ユーザー | POST `/users/me/terms-agreement` | 利用規約同意 |
| 5 | 認証/ユーザー | DELETE `/users/me` | 退会（論理削除） |
| 6 | カプセル | POST `/capsules` | 初回セットアップ（作成） |
| 7 | カプセル | GET `/capsules` | 自分の参加一覧 |
| 8 | カプセル | GET `/capsules/{id}` | 詳細 |
| 9 | カプセル | PATCH `/capsules/{id}/open-date` | 開封日変更（全員可・通知） |
| 9a | カプセル | POST `/capsules/{id}/unseal/prepare` | 開封確認トークン発行（TTL 5分・単回使用。2026-07-03 追記） |
| 10 | カプセル | POST `/capsules/{id}/unseal` | 開封（不可逆・確認トークン） |
| 11 | 参加者 | GET `/capsules/{id}/members` | 参加者一覧 |
| 12 | 参加者 | POST `/capsules/{id}/members` | 招待（メアド） |
| 13 | 参加者 | DELETE `/capsules/{id}/members/{memberId}` | 削除 / 退出 |
| 14 | 参加者 | POST `/invitations/{token}/accept` | 招待受諾 |
| 15 | 配信先 | GET `/capsules/{id}/delivery-addresses` | 配信先一覧 |
| 16 | 配信先 | POST `/capsules/{id}/delivery-addresses` | 配信先追加 |
| 17 | 配信先 | PATCH `/capsules/{id}/delivery-addresses/{addressId}` | 配信先更新 |
| 18 | 配信先 | DELETE `/capsules/{id}/delivery-addresses/{addressId}` | 配信先削除 |
| 19 | 記録 | POST `/capsules/{id}/records` | 記録作成（ソフトブロック） |
| 20 | 記録 | GET `/capsules/{id}/records` | 記録一覧（封印モード表示） |
| 21 | 記録 | GET `/records/{id}` | 記録単体取得 |
| 21a | 記録/エクスポート | POST `/capsules/{id}/export` | エクスポート生成（PDF/JSON/Markdown・全プラン無料・非同期 202） |
| 21b | 記録/エクスポート | GET `/capsules/{id}/export/{jobId}` | エクスポート結果取得（ジョブ状態 / DL URL） |
| 22 | 添付 | POST `/records/{id}/attachments` | presigned URL 発行 |
| 23 | 添付 | POST `/records/{id}/attachments/{attachmentId}/complete` | アップロード完了通知 |
| 24 | 課金(IAP) | POST `/billing/iap/verify` | サブスク購入検証/登録 |
| 25 | 課金(IAP) | GET `/billing/subscription` | 購読状態取得 |
| 26 | 課金(IAP) | POST `/billing/iap/storage` | 追加ストレージ検証（消費型・冪等） |
| 27 | 課金(IAP) | POST `/webhooks/apple/notifications` | Apple ASSN V2 受信 |
| 28 | 課金(IAP) | POST `/webhooks/google/rtdn` | Google RTDN 受信 |

> 開封日到来バッチ・配信ジョブ・バウンスリトライ・トライアル終了バッチは内部ジョブ（§9.2）であり、上記の外部 API には含めない。

**END OF API SPEC**
