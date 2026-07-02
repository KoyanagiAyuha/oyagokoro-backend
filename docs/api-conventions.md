# おやごころ API 規約

> Backend (FastAPI) ⇔ モバイルアプリ (iOS/Android) 連携ルール
> 作成日: 2026-07-02 / 担当: 仕様固めフェーズ

## 1. ベース URL

| 環境 | URL |
|---|---|
| ローカル開発 | `http://localhost:8000` |
| 本番 | `https://api.oyagokoro.lydear.com`（予定。モバイルアプリから直接 HTTPS で疎通） |

すべてのエンドポイントは `/api/v1/` プレフィックス配下。

## 2. リクエスト/レスポンス

- **Content-Type**: `application/json`
- **文字コード**: UTF-8
- **タイムゾーン**: ISO 8601 形式（例: `2026-05-27T00:00:00+09:00`）

## 3. 認証

すべての保護エンドポイントは Firebase Auth の ID Token を Bearer ヘッダーで送信:

```
Authorization: Bearer <Firebase ID Token>
```

トークンの取得はモバイルアプリ（iOS/Android）の Firebase Auth SDK 経由。

## 4. CORS 設定

モバイルアプリ（ネイティブクライアント）からのリクエストは Origin ヘッダーを持たないため、原則として CORS 制限の対象外。ただし開発時の Web ベースツール（Swagger UI 等）やダッシュボード用途を想定し、`CORSMiddleware` は維持する。

### Backend 側設定

`oyagokoro-backend/app/main.py` の `CORSMiddleware` で許可:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,  # .env の CORS_ORIGINS から
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 環境変数

`oyagokoro-backend/.env`:
```
CORS_ORIGINS=http://localhost:8000
```

複数オリジン許可時はカンマ区切り:
```
CORS_ORIGINS=http://localhost:8000,https://api.oyagokoro.lydear.com
```

## 5. エンドポイント命名規則

- リソース名は複数形（例: `/api/v1/capsules`、`/api/v1/records`）
- アクション系は動詞（例: `/api/v1/capsules/{id}/unseal`、`/api/v1/auth/login`）
- ネストは2階層まで

## 6. ステータスコード規約

| ステータス | 用途 |
|---|---|
| 200 OK | 取得・更新成功 |
| 201 Created | 作成成功 |
| 204 No Content | 削除成功 / 内容なし |
| 400 Bad Request | 入力値エラー |
| 401 Unauthorized | 認証失敗・トークン不正 |
| 403 Forbidden | 権限なし（参加者でない等） |
| 404 Not Found | リソース未存在 |
| 409 Conflict | 状態矛盾（例: 開封済みカプセルへの新規参加） |
| 422 Unprocessable Entity | バリデーションエラー（FastAPI デフォルト） |
| 500 Internal Server Error | サーバーエラー |

## 7. エラーレスポンス形式

```json
{
  "detail": "エラーメッセージ（人が読める形式）",
  "code": "ERR_CAPSULE_ALREADY_UNSEALED"
}
```

`detail` は FastAPI のデフォルト形式に従う。

## 8. ヘルスチェック

- パス: `GET /api/v1/health`
- レスポンス: `{ "status": "ok", "db": "ok" }`
- 認証不要

## 9. ローカル疎通確認

Backend 起動後、モバイルアプリ（またはシミュレータ/エミュレータ）から疎通テスト:

```bash
# Backend 起動
uv run uvicorn app.main:app --reload

# 疎通確認（curl でも代用可）
curl http://localhost:8000/api/v1/health
```

期待出力:
```json
{ "status": "ok", "db": "ok" }
```

iOS シミュレータ / Android エミュレータからローカル Backend に接続する場合は、`localhost` ではなく開発機の LAN IP（Android エミュレータは `10.0.2.2`）を利用する。

## 10. IAP（App内課金）関連の連携方針

- 課金処理は Apple App Store / Google Play の IAP を利用し、Backend は決済そのものを扱わない。
- モバイルアプリは購入完了後、レシート/購入トークンを Backend に送信し、Backend がサーバーサイド検証（App Store Server API / Google Play Developer API）を行った上でエンタイトルメントを確定する。
- 詳細な API 定義は `api-spec.md`、データモデルは `data-model.md` を参照。

## 11. Phase 2 想定

- レート制限（slowapi 等）
- API バージョニング (`/api/v2/`)
- WebSocket / プッシュ通知連携（リアルタイム通知）
