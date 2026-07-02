# 社長向け 外部サービス セットアップ手順書

> 対象: おやごころ Phase 1 で社長が手元で実施するサービス設定。
> 部長（バックエンド実装者）側に渡す情報を最後に整理。

---

## 0. Firebase Authentication 追加 Provider（Apple Sign-In）

> 社長判断（2026-06-03）: Phase 1 sign-in provider は **Google + Apple Sign-In 併用**。
> Google は既設定済み。ここでは追加で **Apple Sign-In** の有効化手順を案内する。

### 0.1 ゴール

iOS アプリで Sign in with Apple、Android / Web で Google でログインできる構成にする。バックエンドは Firebase ID Token を verify するだけのため、本セクションは **Firebase Console + Apple Developer Console のみ** の作業。

### 0.2 前提

- Apple Developer Program 加入済み（§2.2 Step 1 を先行実施推奨。$99/年）
- Firebase プロジェクト + Google プロバイダ有効化済み（完了済み）

### 0.3 Apple Developer Console 側の準備

#### Step 1: App ID に Sign in with Apple Capability 追加

1. https://developer.apple.com/account → Certificates, IDs & Profiles → Identifiers
2. iOS アプリ用 Bundle ID（`com.lydear.oyagokoro`）を選択 → Edit
3. **Sign in with Apple** にチェック → Save

#### Step 2: Services ID 作成（Firebase で必要）

1. Identifiers → 「+」 → **Services IDs** → Continue
2. Description: `おやごころ Sign in with Apple`
3. Identifier: `com.lydear.oyagokoro.signin`（Bundle ID とは別の文字列）
4. 作成後、該当 Service ID を選択 → Sign in with Apple → Configure
5. Primary App ID: `com.lydear.oyagokoro` を選択
6. Domains and Subdomains: `<firebase-project-id>.firebaseapp.com`（Firebase Console > プロジェクト設定 > 全般 > プロジェクトID）
7. Return URLs: `https://<firebase-project-id>.firebaseapp.com/__/auth/handler`
8. Save

#### Step 3: Sign in with Apple Key 作成

1. Keys → 「+」
2. 名前: `oyagokoro-firebase-apple-signin`
3. **Sign in with Apple** にチェック → Configure → Primary App ID を選択
4. Continue → Register
5. **.p8 ファイルをダウンロード**（**再ダウンロード不可・確実に保存**）
6. **Key ID**（10桁）をメモ
7. **Team ID** をメモ（右上のアカウント名横に表示される 10桁）

### 0.4 Firebase Console 側の有効化

1. Firebase Console → 該当プロジェクト → Authentication → Sign-in method
2. **Apple** を「使用する」に
3. 以下を入力:
   - **Services ID**: `com.lydear.oyagokoro.signin`（Apple Step 2 のもの）
   - **Apple Team ID**: Apple Step 3 のもの
   - **Key ID**: Apple Step 3 のもの
   - **Private Key**: ダウンロードした .p8 ファイルの内容を**全文貼り付け**（`-----BEGIN PRIVATE KEY-----` から `-----END PRIVATE KEY-----` まで）
4. Save

### 0.5 動作確認

- iOS シミュレータは Sign in with Apple 非対応 → 実機テスト必須（フロントエンド完成後）
- Firebase Console → Authentication → Users で Apple サインインしたユーザーが追加されることを確認

### 0.6 注意

- **バックエンド側の修正は不要**: Firebase ID Token を `verify_id_token()` で検証するだけ（Google / Apple Sign-In どちらも同じパス）
- **Apple Sign-In の relay email**: ユーザーが「Hide My Email」を選択すると `xxxxx@privaterelay.appleid.com` 形式の relay email が返る。バックエンドは relay でも実 email でも受け付ける（B-Slice-1 で email NULL の場合のみ 400 拒否、email があれば OK）

### 0.7 部長に渡す情報

なし（バックエンドコードでの参照は不要。Firebase ID Token の `firebase.sign_in_provider` フィールドに `apple.com` が入るだけ）

---

## 1. Resend（メール配信）

> **前提**: `lydear.com` は既存アプリで Resend 利用済み・ドメイン認証完了（Verified）状態。
> → DNS 設定作業は **不要**。API Key 発行と Webhook 設定だけで完了する。

### 1.1 ゴール

おやごころ用の送信元（`noreply@lydear.com` 等）から Resend 経由でメール送信できるようにする。バウンス検知 Webhook も設定。

### 1.2 手順

1. **API Key 作成**
   - Resend Dashboard → API Keys → 「Create API Key」
   - 名前: `oyagokoro-backend`
   - Permission: **Sending access**（最小権限）
   - Domain: `lydear.com`（既存 Verified ドメインを選択）
   - 表示された `re_xxxxxxxxxx` を控える → 部長に共有
   - ※ 既存アプリ用の API Key を流用せず、おやごころ専用で発行することを推奨（漏洩時の影響範囲を分離）

2. **Webhook 設定**（バウンス検知用）
   - Webhooks → 「Add Webhook」
   - Endpoint URL: 本番 URL 確定前なので **一旦保留 OK**（B-Slice-8 着手時に部長が決定）
   - イベント:
     - `email.bounced`
     - `email.complained`
     - `email.delivered`（任意）
   - 作成後の Signing Secret（`whsec_xxx`）を控える → 部長に共有

3. **送信元アドレスの方針確認**
   - 既存アプリと衝突しないアドレスを決める
   - 推奨: `noreply@lydear.com`（既存アプリで未使用なら）または `oyagokoro@lydear.com`
   - 既存アプリで `noreply@lydear.com` を既に使っているなら、`oyagokoro-noreply@lydear.com` 等で分離
   - 決まった送信元アドレスを部長に共有

### 1.3 部長に渡す情報

```
RESEND_API_KEY=re_xxxxxxxxxx
RESEND_WEBHOOK_SECRET=whsec_xxxxxxxxxx
RESEND_FROM_EMAIL=noreply@lydear.com    # おやごころ用の送信元アドレス
```

### 1.4 注意

- 既存アプリと **送信元アドレスが衝突しないこと** だけ確認してください（重複してても送れますが、運用上混乱します）
- バウンス率は Resend ダッシュボード上で `lydear.com` 全体の合計として表示されます。おやごころ単独のメトリクスが見たくなったらサブドメイン分離を検討（MVP 後で OK）

---

## 2. App Store Connect + Google Play Console（IAP 課金）

> **仕様変更**: モバイル（iOS / Android）ネイティブアプリ化に伴い、Stripe → 各ストアの In-App Purchase に変更。
> **時間がかかる**: 開発者アカウント取得 + アプリ登録 + 審査が必要（Apple 数日〜2週間、Google 数日）

### 2.1 ゴール

両プラットフォームで以下を販売できる状態にする:
- 自動更新サブスクリプション（月額・年額）
- 消費型課金（追加ストレージ 10GB）

バックエンドが両ストアの Server-to-Server 通知を受信して購読状態を同期できる構成。

---

### 2.2 Apple（App Store Connect）

#### Step 1: Apple Developer Program 加入

- https://developer.apple.com にアクセス → Enroll
- **年間 $99**
- 個人なら本人確認のみ、法人なら D-U-N-S 番号取得が必要（取得無料・申請数日）

#### Step 2: App Store Connect でアプリ登録

- https://appstoreconnect.apple.com → マイ App → 「+」→ 新規 App
- バンドル ID: `com.lydear.oyagokoro`（任意・フロント実装と一致させる）
- SKU: `oyagokoro-ios`
- プライマリ言語: 日本語

#### Step 3: IAP 商品作成

App Store Connect → 該当アプリ → 「App 内課金」→ 「管理」→ 商品を追加

**サブスクリプショングループ「premium」を作成し、月額・年額を入れる**（グループ内なら相互切替可能）

| 商品 | タイプ | 商品 ID | 価格 |
|---|---|---|---|
| 月額プラン | 自動更新サブスクリプション | `com.lydear.oyagokoro.premium.monthly` | ¥280（Tier 2）|
| 年額プラン | 自動更新サブスクリプション | `com.lydear.oyagokoro.premium.yearly` | ¥2,600 前後（Tier から選択）|
| ストレージ10GB | 消費型 | `com.lydear.oyagokoro.storage.10gb` | ¥1,500（Tier）|

- **Apple の価格は Pricing Tier から選択**。280円・2,520円ピッタリは無理なので近似値（年額は手数料差し引きで月額×10〜12 の値）
- 無料試用 7日間はサブスク設定で「導入価格」→「無料」で7日

#### Step 4: App Store Server API キー取得（バックエンド側で領収書検証 / 購読状態取得に必要）

- App Store Connect → ユーザーとアクセス → 統合 → 「App Store Server API」タブ
- 「キーを生成」
- 名前: `oyagokoro-backend`
- アクセス: 「App Manager」または「Developer」
- 発行後、**.p8 ファイルをダウンロード**（再ダウンロード不可、確実に保存）
- **Issuer ID** / **Key ID** もメモ
- 部長に渡す: .p8 ファイル + Issuer ID + Key ID

#### Step 5: App Store Server Notifications V2 設定

- App Store Connect → 該当アプリ → App 情報 → App Store Server Notifications
- Production Server URL / Sandbox Server URL: **B-Slice-7 着手時に部長が設定**（今は保留）
- バージョン: V2 を選択
- ※ サブスク更新・解約・払戻し等が自動でバックエンドに通知される

---

### 2.3 Google（Google Play Console）

#### Step 1: 開発者アカウント登録

- https://play.google.com/console
- **登録料 $25（一回のみ）**
- 個人 / 法人どちらでも

#### Step 2: アプリ登録

- 「アプリを作成」
- アプリ名: おやごころ
- パッケージ名: `com.lydear.oyagokoro`（Apple と統一推奨）
- 無料 / 有料: 「無料」（アプリ自体は無料、IAP で課金）

#### Step 3: IAP 商品作成

Play Console → 該当アプリ → 収益化 → 商品

| 商品 | タイプ | 商品 ID | 価格 |
|---|---|---|---|
| 月額プラン | 定期購入 | `premium_monthly` | ¥280 |
| 年額プラン | 定期購入 | `premium_yearly` | ¥2,520 |
| ストレージ10GB | アプリ内アイテム（管理対象） | `storage_10gb` | ¥1,500 |

- **Google は価格自由**（厳密に 280円・2,520円可能）
- 無料試用 7日間は定期購入の「基本プラン」で設定

#### Step 4: Service Account 作成（Play Developer API 用）

バックエンドが Play から購読情報を取得するため。

- **既存の Firebase プロジェクトと同じ GCP プロジェクトを使う**のが楽（おやごころ Firebase が動いてる GCP）
- Google Cloud Console → IAM と管理 → サービスアカウント → 「サービスアカウントを作成」
- 名前: `oyagokoro-play-billing`
- ロール: 一旦付けず、後で Play Console 側で権限付与
- 作成後、該当サービスアカウント → 「鍵」タブ → 「鍵を追加」→「新しい鍵を作成」→ JSON
- ダウンロードした JSON を部長に共有（**`.gitignore` 必須**）

#### Step 5: Play Console でサービスアカウント招待

- Play Console → 設定 → デベロッパー アカウント → API アクセス
- 「新しいサービスアカウントを使用してリンク」または上記サービスアカウントの email を招待
- 権限:
  - 「財務データを表示」
  - 「注文と購読の管理」

#### Step 6: Real-time Developer Notifications (RTDN)

サブスク更新・解約等の通知を Pub/Sub 経由でバックエンドが受信する。

- Google Cloud Console → Pub/Sub → トピック作成
- トピック名: `oyagokoro-iap-notifications`
- サービスアカウント `oyagokoro-play-billing` に「Pub/Sub サブスクライバー」ロール付与
- Play Console → 収益化 → 収益化のセットアップ → 「Cloud Pub/Sub」
- トピックのフルパス入力: `projects/<GCPプロジェクトID>/topics/oyagokoro-iap-notifications`
- ※ サブスクライブ実装は B-Slice-7 着手時に部長が対応

---

### 2.4 部長に渡す情報

```
# Apple App Store
APPLE_BUNDLE_ID=com.lydear.oyagokoro
APPLE_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
APPLE_KEY_ID=ABCDEFGHIJ
APPLE_PRIVATE_KEY_PATH=./AuthKey_ABCDEFGHIJ.p8     # .p8 ファイル配置（.gitignore 必須）
APPLE_PRODUCT_MONTHLY=com.lydear.oyagokoro.premium.monthly
APPLE_PRODUCT_YEARLY=com.lydear.oyagokoro.premium.yearly
APPLE_PRODUCT_STORAGE_10GB=com.lydear.oyagokoro.storage.10gb
APPLE_USE_SANDBOX=true                              # 開発時 true、本番リリース時 false

# Google Play
GOOGLE_PACKAGE_NAME=com.lydear.oyagokoro
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_PATH=./oyagokoro-play-billing-xxxx.json  # .gitignore 必須
GOOGLE_PUBSUB_TOPIC=projects/<gcp-project-id>/topics/oyagokoro-iap-notifications
GOOGLE_PRODUCT_MONTHLY=premium_monthly
GOOGLE_PRODUCT_YEARLY=premium_yearly
GOOGLE_PRODUCT_STORAGE_10GB=storage_10gb
```

### 2.5 注意

- **アプリの審査通過前でも IAP 商品の作成・テスト購入は可能**（TestFlight / 内部テストトラックで動作確認できる）
- **テスト購入**:
  - Apple: TestFlight 内部テスター登録 + Sandbox Apple ID
  - Google: 内部テストトラック + ライセンステスター登録
- **本番リリース**: 両ストアの審査必要（Apple 数日〜2週間、Google 数日〜1週間）
- **手数料**: 売上の 30%（年間売上 1億円未満なら **小規模事業者プログラム適用で 15%**。両ストアとも申請可）
- **価格変更**は両ストアの管理画面から実施（バックエンド側は商品 ID で照合するので無関係）

---

## 3. AWS（子アカウント + スイッチロール + CLI プロファイル）

> メインアカウントは AWS Organizations のルートとして利用。
> おやごころ用の子アカウントを作成し、メインから IAM Role でスイッチする構成。

### 3.1 ゴール

- メインアカウントから `aws --profile oyagokoro <command>` で子アカウントの S3 を操作できる
- バックエンドアプリ用の最小権限 IAM ユーザーを子アカウント内に作成し、アクセスキーを発行

### 3.2 手順

#### Step 1: 子アカウント作成（AWS Organizations）

1. メインアカウントのルートユーザー（または Organizations 管理権限を持つ IAM ユーザー）でログイン
2. AWS Organizations → AWS アカウント → **「AWS アカウントを追加」 → 「AWS アカウントを作成」**
3. 入力:
   - AWS アカウント名: `oyagokoro-prod`
   - メールアドレス: メインと別のもの（Gmail のエイリアス `you+oyagokoro@gmail.com` でも可）
   - IAM ロール名: `OrganizationAccountAccessRole`（デフォルトのまま）
4. 作成完了後、表示される **子アカウント ID（12桁）** をメモ
5. リージョン: 後の作業はすべて `ap-northeast-1`（東京）

#### Step 2: 子アカウントにスイッチ用 IAM Role を作成

1. メインアカウントのコンソールで右上のアカウント名 → 「ロールの切り替え」
   - Account: 子アカウント ID
   - Role: `OrganizationAccountAccessRole`
   - → 子アカウントの管理者として操作できる
2. 子アカウントの IAM → ロール → 「ロールを作成」
   - 信頼されたエンティティタイプ: **AWS アカウント**
   - AWS アカウント: 「別の AWS アカウント」 → **メインアカウント ID** を入力
   - 「MFA が必要」にチェック（**強く推奨**）
   - 権限ポリシー: `AdministratorAccess`（管理用なのでフル権限）
   - ロール名: `OyagokoroAdminRole`
   - 説明: メインアカウントからスイッチして子アカウントを管理する用
3. 作成後の **ロール ARN**（`arn:aws:iam::<子ID>:role/OyagokoroAdminRole`）をメモ

#### Step 3: メインアカウントの IAM ユーザーに AssumeRole 権限を付与

メインで使っている IAM ユーザーに、子アカウントの `OyagokoroAdminRole` を引き受ける権限を付与する。

1. メインアカウントの IAM → ユーザー → 自分のユーザー → 許可
2. 「インラインポリシーを追加」または既存ポリシーに追記:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "sts:AssumeRole",
      "Resource": "arn:aws:iam::<子アカウントID>:role/OyagokoroAdminRole"
    }
  ]
}
```

ポリシー名: `AssumeOyagokoroAdminRole`

#### Step 4: ローカル CLI プロファイル設定

ローカルで `~/.aws/credentials` と `~/.aws/config` を編集。

**`~/.aws/credentials`**（メインアカウントの IAM ユーザーのキー）
```ini
[main]
aws_access_key_id = AKIAXXXXXXXXXX
aws_secret_access_key = xxxxxxxxxx
```

**`~/.aws/config`**
```ini
[profile main]
region = ap-northeast-1
output = json

[profile oyagokoro]
role_arn = arn:aws:iam::<子アカウントID>:role/OyagokoroAdminRole
source_profile = main
region = ap-northeast-1
mfa_serial = arn:aws:iam::<メインアカウントID>:mfa/<IAMユーザー名>
```

- `mfa_serial` は MFA デバイス ARN（IAM ユーザーのセキュリティ認証情報 → MFA デバイス で確認）。MFA 必須にしていない場合は省略可
- `<IAMユーザー名>` は メインで使っている IAM ユーザー名

#### Step 5: 動作確認

```bash
aws sts get-caller-identity --profile oyagokoro
# MFA 設定済みなら 6桁コードが聞かれる
# → 結果に "Arn": "arn:aws:sts::<子ID>:assumed-role/OyagokoroAdminRole/..." が返れば成功
```

#### Step 6: S3 バケット作成（B-Slice-9 着手時でも OK）

```bash
aws s3 mb s3://oyagokoro-media-prod --region ap-northeast-1 --profile oyagokoro
```

詳細設定（CORS、ライフサイクル、暗号化）は B-Slice-9 着手時に部長側で実施可能。

#### Step 7: バックエンドアプリ用 IAM ユーザー作成

バックエンドが S3 にアクセスするための専用 IAM ユーザーを **子アカウント内に** 作成（プログラマティックアクセス専用）。

1. 子アカウントの IAM → ユーザー → 「ユーザーの作成」
   - ユーザー名: `oyagokoro-backend-app`
   - アクセスタイプ: アクセスキーのみ（コンソールアクセス不要）
2. 権限ポリシー: 「ポリシーを直接アタッチ」→「ポリシーを作成」
   - JSON:
   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": [
           "s3:PutObject",
           "s3:GetObject",
           "s3:DeleteObject",
           "s3:ListBucket"
         ],
         "Resource": [
           "arn:aws:s3:::oyagokoro-media-prod",
           "arn:aws:s3:::oyagokoro-media-prod/*"
         ]
       }
     ]
   }
   ```
   - ポリシー名: `OyagokoroBackendS3Access`
3. 作成後、ユーザー → セキュリティ認証情報 → アクセスキーを作成
   - 用途: 「他」または「アプリケーション」
   - 表示される **AccessKeyId / SecretAccessKey** をコピー → 部長に共有

### 3.3 部長に渡す情報

```
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxx           # oyagokoro-backend-app ユーザーのキー
AWS_SECRET_ACCESS_KEY=xxxxxxxxxx
AWS_S3_BUCKET=oyagokoro-media-prod
AWS_REGION=ap-northeast-1
```

加えて、部長側で `--profile oyagokoro` を使った CLI 作業（S3 設定変更など）が必要になった場合に備え、CLI プロファイル名（`oyagokoro`）も共有。

---

## 4. 全体まとめ: 部長に渡す情報一覧

社長作業完了後、以下の値を部長に共有してください（Slack DM や Notion など、リポジトリ外で）。

```
# Resend
RESEND_API_KEY=re_xxxxxxxxxx
RESEND_WEBHOOK_SECRET=whsec_xxxxxxxxxx
RESEND_FROM_EMAIL=noreply@lydear.com

# Apple App Store
APPLE_BUNDLE_ID=com.lydear.oyagokoro
APPLE_ISSUER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
APPLE_KEY_ID=ABCDEFGHIJ
APPLE_PRIVATE_KEY_PATH=./AuthKey_ABCDEFGHIJ.p8
APPLE_PRODUCT_MONTHLY=com.lydear.oyagokoro.premium.monthly
APPLE_PRODUCT_YEARLY=com.lydear.oyagokoro.premium.yearly
APPLE_PRODUCT_STORAGE_10GB=com.lydear.oyagokoro.storage.10gb
APPLE_USE_SANDBOX=true

# Google Play
GOOGLE_PACKAGE_NAME=com.lydear.oyagokoro
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_PATH=./oyagokoro-play-billing-xxxx.json
GOOGLE_PUBSUB_TOPIC=projects/<gcp-project-id>/topics/oyagokoro-iap-notifications
GOOGLE_PRODUCT_MONTHLY=premium_monthly
GOOGLE_PRODUCT_YEARLY=premium_yearly
GOOGLE_PRODUCT_STORAGE_10GB=storage_10gb

# AWS
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxx
AWS_S3_BUCKET=oyagokoro-media-prod
AWS_REGION=ap-northeast-1
AWS_CLI_PROFILE=oyagokoro  # ローカル CLI 作業用（参考）
```

部長は受領後 `.env` に転記します（`.env` は `.gitignore` 済み）。
**`.p8` ファイル / Play サービスアカウント JSON も `.gitignore` 対応済み**（手順書 §6 参照）。

---

## 5. 推奨着手タイミング

| サービス | いつ着手 | 理由 |
|---|---|---|
| Resend | B-Slice-8 着手の前日でも可 | DNS 認証済みのため API Key 発行 + Webhook 設定の 5〜10分作業 |
| **Apple Developer** | **今すぐ着手推奨** | 個人なら即日、法人は D-U-N-S 取得に数日。アプリ審査もあるので早めに |
| **Google Play Console** | **今すぐ着手推奨** | $25 払って即日アクセス可能。商品作成は B-Slice-7 直前でも可 |
| AWS | B-Slice-9 着手の前週 | 子アカウント作成 + プロファイル動作確認 |

**Apple / Google の開発者アカウント取得が Phase 1 全体のクリティカルパス** になる可能性があります。バックエンド実装は IAP なしで B-Slice-1〜6 まで進められますが、B-Slice-7（課金）着手前にアカウント + アプリ登録 + 商品作成までは完了している必要があります。

---

## 6. .gitignore 対応（部長作業メモ）

- `*-firebase-adminsdk-*.json` — Firebase Service Account（対応済み）
- `*.p8` — Apple App Store Server API キー（B-Slice-7 着手時に追加予定）
- `oyagokoro-play-billing-*.json` — Google Play サービスアカウント（B-Slice-7 着手時に追加予定）
