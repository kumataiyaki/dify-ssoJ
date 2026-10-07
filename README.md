# dify-ssoJ（日本語ドキュメント版）

Dify Community 版（セルフホスト）に OIDC のシングルサインオン（SSO）を追加する、**非公式**の外部サービスです。

このリポジトリは [lockdlock/dify-ssoJ](https://github.com/lockdlock/dify-ssoJ) の公開フォークです。変えたのはドキュメントの日本語化だけで、アプリケーションコードは上流のままです。

- セットアップ手順（社内 CA 証明書の手順、トラブルシューティングを含む）: **[docs/SETUP_ja.md](docs/SETUP_ja.md)**
- 元の中国語 README: [docs/README_zh.md](docs/README_zh.md)
- 最初の元プロジェクト（lework/dify-sso）の README（中国語）: [README_ORIGIN.md](README_ORIGIN.md)

> [!WARNING]
> 上流の最新コミット（`86b4f58`、2026-07-17）には、**そのままではビルドも起動もできない不具合**があります。使う前に「[既知の問題](#5-既知の問題上流-86b4f58-時点)」を読んでください。

---

## 1. 概要

Dify の SSO ログインは、本来は Enterprise 版の機能です。dify-sso は、Dify のフロントエンドが Enterprise 版向けに呼び出す API の一部を代わりに実装（モック）します。これにより Community 版のログイン画面に「SSO でログイン」ボタンが表示され、OIDC に対応した IdP（Keycloak、Casdoor など）でログインできるようになります。Dify 本体のソースコードには手を加えません。

コードで確認した主な機能は次のとおりです。

- OIDC の Authorization Code Flow による Dify コンソールへのログイン（`app/api/dify/sso.py`）
- 初回ログイン時に Dify アカウントを自動作成し、`TENANT_ID` で指定したワークスペースに参加させる（`app/services/oidc.py`）
- WebApp（公開アプリ）の SSO ログインと、アプリごとのアクセス制御。アクセスモードは Redis の `webapp_access_mode:*` キーに保存されます（`app/api/dify/webapp.py`）
- `/console/api/system-features` が返す値の切り替え。ログイン方法、プラグインのインストール元、DSL バージョンなどを環境変数で設定できます（`app/configs/feature_config.py`、`app/api/dify/enterprise.py`）

## 2. 仕組み

```text
ブラウザ ─▶ Dify の Nginx ─┬─ /console/api/system-features  ─┐
                           ├─ /console/api/enterprise/sso/    ├─▶ dify-sso コンテナ（ポート 8000）
                           ├─ /console/api/enterprise/webapp/ │     ├─▶ Dify の PostgreSQL（accounts / tenant_account_joins など）
                           ├─ /api/enterprise/               ─┘     ├─▶ Dify の Redis（リフレッシュトークン、WebApp のアクセスモード）
                           │                                        └─▶ IdP（OIDC の discovery / token / userinfo）
                           └─ 上記以外 ─▶ Dify 本体（api / web）
```

- **Nginx での振り分け**: Dify の Nginx 設定（`docker/nginx/conf.d/default.conf.template`）に 4 つの `location` を追加して、上の 4 つのパスを dify-sso コンテナ（`http://dify-sso:8000`）に送ります。どれも `/console/api` より上に書く必要があります。
- **PostgreSQL と Redis を Dify と共有**: dify-sso は Dify と同じ DB に接続し、`accounts` と `tenant_account_joins` テーブルを直接読み書きします（`app/models/account.py`）。Redis もリフレッシュトークンの保存などで共有します。
- **トークンは Dify の `SECRET_KEY` で署名**: アクセストークンと CSRF トークンは、Dify と同じ `SECRET_KEY` を使って HS256 で署名した JWT です（`app/services/passport.py`）。`SECRET_KEY` が Dify と違っていると、ログインしても Dify に認識されません。
- **ログインの流れ**（`app/api/dify/sso.py`）
  1. `GET /console/api/enterprise/sso/oidc/login` で IdP の認可 URL を返す
  2. IdP で認証したあと、`GET /console/api/enterprise/sso/oidc/callback` で認可コードをトークンに交換して userinfo を取得する（`app/services/oidc.py:71-99`）
  3. `access_token` / `refresh_token` / `csrf_token` の Cookie を発行し、`CONSOLE_WEB_URL` にリダイレクトする。`CONSOLE_WEB_URL` が `https` で始まるときは、`__Host-` 付きの Cookie も発行する（`app/services/token.py:17-23, 68-78`）
- **初回ログイン時のアカウント自動作成とロール**（`app/services/oidc.py:110-160`）
  - userinfo の `email` でアカウントを探します。`email` がない場合はエラーになります。`name` がない場合は、メールアドレスの `@` より前の部分を表示名にします。
  - アカウントがなければ作成します。新しいアカウントの既定値は `interface_language="ja-JP"`、`timezone="Asia/Tokyo"` です（`app/models/account.py:195-205`）。作成したアカウントは `TENANT_ID` のワークスペースに参加させます。
  - 参加時のロールは次の順で決まります。まず `ACCOUNT_DEFAULT_ROLE` を使います（無効な値の場合は `normal`）。userinfo の **`roles` クレーム**（トップレベルの配列）に `admin`、`editor`、`normal` が含まれていれば、`admin` → `editor` → `normal` の優先順でそちらを使います。
  - **すでにワークスペースのメンバーになっている人のロールは上書きしません。** 2 回目以降のログインでは、Dify 側で設定したロールが優先されます（`oidc.py:158-160`）。
  - Dify 上に同じメールアドレスのローカルアカウントがすでにあれば、そのアカウントでログインします。

## 3. 対応 Dify バージョン

| 状況 | 内容 | 根拠 |
| --- | --- | --- |
| 推奨 | Dify `1.14.1` 以降 | xjfyt 版 README（[docs/README_zh.md](docs/README_zh.md)） |
| xjfyt 版で動作確認済み | `1.13.3`、`1.14.0`、`1.14.1` | 同上 |
| 1.13.x で使う場合 | `LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT=true` を設定する | `app/configs/feature_config.py:15-21` |
| 1.15.0 | lockdlock 版で 1.15.0 向けの修正が入っていますが、その修正自体に構文エラーがあります（**要確認**） | コミット `efe219c` |

- モックのレスポンスは Dify 1.14.0 のスキーマに合わせてあります（`app/api/dify/enterprise.py:22`）。
- `APP_DSL_VERSION`（既定値 `0.6.0`）は、使っている Dify の `api/constants/dsl_version.py` に書かれている値に合わせてください。
- このフォークでは、実際の Dify と組み合わせた動作確認はしていません。

## 4. 上流からの変更点

### xjfyt/dify-sso（lework/dify-sso からの主な変更）

- Dify 1.13〜1.14 系への対応と、中国語のセットアップドキュメントの追加
- Dify 側で設定したロールを優先し、SSO でログインするたびにロールを上書きしないように変更
- `/console/api/apps` 系のリバースプロキシ（`app/api/dify/apps_proxy.py`）を追加。`access_mode` を補って、Dify 1.14.1 で起きる React #130 のクラッシュを回避する
- モックの値を環境変数で設定できるように変更（`feature_config.py`）
- `tenant_account_joins.current` が設定されない問題（`/profile` が 500 エラーになる）と、アバター同期の不具合を修正
- `TIMEZONE` 環境変数、uv を使ったマルチステージ Dockerfile、`ghcr.io/xjfyt/dify-sso:latest`（amd64 / arm64）を公開する GitHub Actions を追加

### lockdlock/dify-ssoJ（xjfyt 版からの変更。すべて 2026-07-17 のコミット）

- **タイムゾーンを日本向けに変更**: `TIMEZONE` の既定値を `Asia/Tokyo` にした（`app/configs/app_config.py:58-63`）。新しく作るアカウントの既定値も `ja-JP` / `Asia/Tokyo` にした（`app/models/account.py:202-203`）
- **CA 証明書への対応**（Dockerfile、コミット `86b4f58`「Update Dockerfile」）: `ca-certificates` をインストールし、社内 CA 証明書 `tslabCA.crt` をイメージに入れて `update-ca-certificates` を実行する。あわせて `REQUESTS_CA_BUNDLE` と `SSL_CERT_FILE` を設定する。詳しくは [SETUP_ja.md の B 章](docs/SETUP_ja.md#b-社内-ca-証明書を使う場合)を参照
- **Dify 1.15.0 向けの変更**（`app/api/dify/webapp.py`）: `installed_apps.id` を `app_id` に変換する処理、`ACCESS_SUBJECT_TYPE_*` 形式への対応、`/webapp/permission/batch` での `appIds` の受け付け（未完成。後述）
- Nginx 設定例で振り分けるパスに `/console/api/enterprise/webapp/` と `/api/enterprise/` を追加し、`X-Csrf-Token` ヘッダーを転送するように変更
- 一部のコメントとログメッセージを英語・日本語に翻訳

### このフォーク（kumataiyaki/dify-ssoJ）

- `README.md` を日本語で書き直し、元の中国語 README を `docs/README_zh.md` に移動
- `docs/SETUP_ja.md` を追加
- `.env.example` に日本語のコメントを追加（キーと値は変更なし）
- アプリケーションコード、Dockerfile、LICENSE は変更していません

## 5. 既知の問題（上流 `86b4f58` 時点）

コードを読んで確認した問題です。このフォークではコードを修正していないので、**使う前に各自で対処してください**。修正方法は [SETUP_ja.md の「A-3. ビルド前の確認」](docs/SETUP_ja.md#a-3-ビルド前の確認既知の問題への対処)にまとめています。

1. **`app/api/dify/webapp.py:398` 以降のインデントが崩れていて、`IndentationError` が出る**。`check_permission()` が関数の外に出てしまっており、`appIds` も定義されていません。このモジュールは起動時に読み込まれるので、**このままでは dify-sso が起動しません**。Python 3.11 で import して、エラーになることを確認しました。
2. **Dockerfile の 25 行目の行末に、行継続の `\` がない**。BuildKit の Dockerfile パーサーで `unknown instruction: REQUESTS_CA_BUNDLE=...`（26 行目）のエラーになることを確認しました。このままではビルドできません。
3. **Dockerfile の 41 行目が、リポジトリにない `tslabCA.crt` を `COPY` している**。リポジトリ直下に CA 証明書を置かないと、ビルドが失敗します。
4. **公開されているイメージ `ghcr.io/xjfyt/dify-sso:latest` は、xjfyt 版のコミット `a2b5bb5` からビルドされたもの**です（イメージのラベルで確認）。lockdlock 版の変更（Asia/Tokyo、CA 証明書、1.15 向けの修正）は入っていません。
5. **コンソールのログインで保存するリフレッシュトークンの有効期限が約 30 秒になる**。`app/services/account.py:33-38` が、日数の設定値（`REFRESH_TOKEN_EXPIRE_DAYS=30`）を秒数として Redis の `SETEX` に渡しているためです。アクセストークンの期限（`ACCESS_TOKEN_EXPIRE_MINUTES`）が切れたあとにトークンを更新できず、再ログインが必要になる可能性があります（**要確認**）。
6. OIDC の `state` パラメータが固定値（`random_state`）で、コールバックでも検証していません（`app/services/oidc.py:62`）。また、IdP への HTTP リクエストにタイムアウトが設定されていません。
7. `.env.example` の `TIMEZONE` は `Asia/Shanghai` で、コードの既定値（`Asia/Tokyo`）と違います。`yaml/docker-compose.yaml` もサンプル値のままです（`TENANT_ID` に空白が入っているなど）。
8. `/console/api/apps` のプロキシ（`apps_proxy.py`）は、上流の Nginx 設定例では振り分けの対象になっていません。Dify 1.14.1 でアプリ設定パネルが React #130 でクラッシュする場合は、別途振り分けが必要かもしれません（**要確認**）。

## 6. 注意事項

- **非公式のソフトウェアです。** Dify（LangGenius）とは関係がなく、サポートもありません。
- **Dify の内部 API と DB スキーマに依存しています。** フロントエンドが呼び出す API のレスポンス形式、`accounts` / `tenant_account_joins` / `sites` / `installed_apps` などのテーブル構造、Cookie や JWT の仕様が変わると、Dify をアップデートしたときに**動かなくなる可能性があります**。
- **Dify 公式の SSO は Enterprise 版の機能です。** このソフトウェアを使うことが Dify のライセンスや利用規約に照らして問題ないかは、**利用者ご自身で確認してください**。元プロジェクトの README にも、Dify の商用ライセンスを尊重する旨の声明があります（[README_ORIGIN.md](README_ORIGIN.md) の「特别声明」）。
- dify-sso は Dify の DB に直接書き込みます。**本番環境に入れる前に、必ず検証環境で試してください。** DB のバックアップも取っておいてください。
- **Dify のバージョンは固定することをおすすめします。** `main` ブランチや `latest` タグではなく、リリースタグを使ってください。アップデートするときは、検証環境で確認してから本番環境に反映してください。

## 7. ドキュメント

| ファイル | 内容 |
| --- | --- |
| [docs/SETUP_ja.md](docs/SETUP_ja.md) | 日本語のセットアップ手順（標準手順、社内 CA 証明書の手順、トラブルシューティング、アップデート時の注意） |
| [.env.example](.env.example) | 環境変数のサンプル（日本語コメント付き） |
| [docs/README_zh.md](docs/README_zh.md) | 元の中国語 README（xjfyt 版。Nginx 設定例は lockdlock 版で更新） |
| [README_ORIGIN.md](README_ORIGIN.md) | lework/dify-sso の README（中国語） |
| [yaml/docker-compose.yaml](yaml/docker-compose.yaml)、[yaml/k8s-deployment.yaml](yaml/k8s-deployment.yaml) | 上流のデプロイ例（サンプル値） |

## 8. ライセンスとクレジット

- ライセンス: [MIT License](LICENSE)。上流の LICENSE（Copyright (c) 2025 Lework）をそのまま残しています。
- このリポジトリは次のプロジェクトを受け継いでいます。
  1. [lework/dify-sso](https://github.com/lework/dify-sso): オリジナル
  2. [xjfyt/dify-sso](https://github.com/xjfyt/dify-sso): 新しい Dify への対応、設定の環境変数化など
  3. [lockdlock/dify-ssoJ](https://github.com/lockdlock/dify-ssoJ): Asia/Tokyo への変更、CA 証明書への対応、Dify 1.15 向けの変更
  4. このリポジトリ（[kumataiyaki/dify-ssoJ](https://github.com/kumataiyaki/dify-ssoJ)）: 日本語ドキュメントの追加

各プロジェクトの作者の皆さまに感謝します。
