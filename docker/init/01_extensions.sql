-- Neon 互換: pgcrypto 拡張を有効化（gen_random_uuid() 用）
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- タイムゾーン設定（コンテナ全体は TZ 環境変数で設定済みだが、PG セッションレベルでも確認）
SET TIME ZONE 'Asia/Tokyo';
