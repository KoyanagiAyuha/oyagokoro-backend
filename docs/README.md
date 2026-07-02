# ドキュメント索引

このリポジトリ（`oyagokoro-backend`）は自己完結しています。旧 `oyagokoro/` リポジトリへの参照は不要です。仕様・データモデル・API定義・外部サービス設定は、すべて本リポジトリの `docs/` 配下に揃っています。

課金は Apple/Google の **IAP（App内課金）** を採用しています（Stripe は使用しません）。フロントエンドは **モバイルネイティブアプリ（iOS/Android）** を前提としています。

## ドキュメント一覧（読む順序）

1. **[product-spec.md](./product-spec.md)** — 製品仕様（機能要件・ユーザーフロー・ビジネスルールの理想形）
2. **[data-model.md](./data-model.md)** — データモデル設計（テーブル構成・ER関係・IAPエンタイトルメント設計）
3. **[api-spec.md](./api-spec.md)** — APIエンドポイント仕様（リクエスト/レスポンス定義）
4. **[api-conventions.md](./api-conventions.md)** — API連携規約（認証・命名規則・ステータスコード等の横断ルール）
5. **[owner-setup-guide.md](./owner-setup-guide.md)** — 外部サービス設定手順（Firebase / IAP / Resend / AWS S3 等）

## 補足

- DDL（実際のテーブル定義）は `alembic/versions/` 配下のマイグレーションファイルが真実の源（Source of Truth）。`data-model.md` は設計意図を示すドキュメントとして参照する。
- 各ドキュメントは実装進捗やギャップを記載せず、理想形の仕様のみを記述する。
