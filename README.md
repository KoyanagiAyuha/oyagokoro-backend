# おやごころ Backend

家族の20年タイムカプセル — バックエンドAPI

## 技術スタック

- Python 3.12 / FastAPI / uv 管理
- PostgreSQL 16（ローカルは Docker / 本番は Neon Serverless Postgres）
- SQLAlchemy 2.x (async) + Alembic
- Firebase Auth / Stripe / Resend / AWS S3 連携（実装は順次）

## 必要なもの

- Python 3.12 以上
- uv（インストール: `curl -LsSf https://astral.sh/uv/install.sh | sh`）
- Docker Desktop（PostgreSQL ローカル起動用）

## 初回セットアップ

### 1. 依存パッケージのインストール

```bash
uv sync
```

### 2. 環境変数の設定

```bash
cp .env.sample .env
# 必要に応じて値を編集（ローカル DB のみなら DATABASE_URL は変更不要）
```

### 3. PostgreSQL（Docker）起動

```bash
docker compose up -d
docker compose ps  # STATUS が Up (healthy) になることを確認
```

### 4. データベースマイグレーション

```bash
uv run alembic upgrade head
```

## 開発

### サーバー起動

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API ドキュメント: http://localhost:8000/docs
- ヘルスチェック: http://localhost:8000/api/v1/health

### コードフォーマット・Lint

```bash
uv run ruff format .
uv run ruff check .
```

### テスト

```bash
uv run pytest
```

### Alembic マイグレーション

新しいマイグレーションファイル生成:

```bash
uv run alembic revision --autogenerate -m "<変更内容>"
```

適用:

```bash
uv run alembic upgrade head
```

ロールバック（1つ前へ）:

```bash
uv run alembic downgrade -1
```

## ディレクトリ構成

```
oyagokoro-backend/
├── app/
│   ├── main.py              # FastAPI アプリ本体
│   ├── settings.py          # 環境変数設定
│   ├── database.py          # SQLAlchemy async engine
│   ├── models/              # SQLAlchemy モデル（11テーブル）
│   ├── api/v1/              # API エンドポイント
│   └── schemas/             # Pydantic スキーマ
├── alembic/                 # マイグレーション
│   ├── env.py
│   └── versions/
├── tests/
├── docker/
│   ├── init/                # PostgreSQL 拡張機能初期化
│   └── volumes/             # DB データ永続化（.gitignore対象）
├── docker-compose.yml
├── pyproject.toml
└── .env.sample
```

## 関連ドキュメント

- データモデル設計: `../oyagokoro/docs/data-model.md`
- 仕様書: `../oyagokoro/specs/oyagokoro-spec.md`
- DDL（参考）: `../oyagokoro/db/schema.sql`

## API 規約

- ベースパス: `/api/v1/`
- コンテントタイプ: `application/json`
- 認証ヘッダー: `Authorization: Bearer <Firebase ID Token>`

## トラブルシューティング

### Docker 起動でポート競合

5432 が既に使われている場合は `docker-compose.yml` のポートマッピングを変更（例: `15432:5432`）し、`.env` の `DATABASE_URL` も合わせて変更。

### alembic upgrade で外部キーエラー

DB を一旦リセット: `docker compose down -v && docker compose up -d` してから `uv run alembic upgrade head`。

## ライセンス

Private — All rights reserved.
