# dify-ssoJ セットアップ手順（日本語）

Dify Community 版（Docker Compose で構築したもの）に dify-ssoJ を追加して、Keycloak などの OIDC IdP でログインできるようにする手順です。

> [!IMPORTANT]
> - 非公式のソフトウェアです。Dify の内部 API と DB に依存しています。**必ず検証環境で先に試し**、DB のバックアップを取ってから作業してください。
> - このフォークのソースからビルドしてください。上流 `86b4f58` にあった、起動やビルドができない不具合はこのフォークで修正済みです（[README の「既知の問題と修正状況」](../README.md#5-既知の問題と修正状況)）。
> - 「**要確認**」と書いた箇所は、コードや資料からは確定できなかった点、または実機で検証していない点です。

この手順で使う値の例です。実際の環境に合わせて読み替えてください。

| 項目 | 例 |
| --- | --- |
| Dify の URL | `https://dify.example.com` |
| Dify の配置場所 | `${DIFY_DIR}`（`docker/` ディレクトリを含む Dify リポジトリ） |
| Dify の Docker ネットワーク | `docker_default` |
| dify-sso のコンテナ名とポート | `dify-sso`、`8000`（gunicorn が `0.0.0.0:8000` で待ち受けます。Dockerfile の 47 行目） |
| Keycloak | `https://keycloak.example.local`、レルム `myrealm` |
| dify-sso の作業ディレクトリ | `/opt/dify-ssoJ` |

---

## A. 標準手順

### A-1. 前提条件

- Docker と Docker Compose（Dockerfile が `RUN --mount=type=cache` を使っているので、BuildKit が使える Docker が必要です。Docker 23 以降は BuildKit が既定で有効です）
- Docker Compose で動いている Dify（推奨は 1.14.1 以降。リリースタグでバージョンを固定してください）
- dify-sso を Dify と同じホストに置き、Dify の PostgreSQL と Redis に接続できること
- OIDC に対応した IdP（この手順では Keycloak を例にします）
- ユーザーの userinfo に **`email`** が含まれること。`email` がないとログインできません（`app/services/oidc.py:121-123`）

### A-2. ソースの取得

```bash
git clone https://github.com/kumataiyaki/dify-ssoJ.git /opt/dify-ssoJ
cd /opt/dify-ssoJ
```

### A-3. 社内 CA 証明書の配置（必要な場合のみ）

IdP（Keycloak など）の HTTPS 証明書が社内 CA で署名されている場合は、ビルドの前に社内 CA の証明書（PEM 形式、拡張子 `.crt`）を `certs/` に置きます。詳しくは [B 章](#b-社内-ca-証明書を使う場合)を参照してください。公的な CA の証明書を使っている IdP なら、何もしなくて構いません（`certs/` が空でもビルドできます）。

### A-4. `.env` の作成

```bash
cp .env.example .env
chmod 600 .env
```

`.env` は `docker run --env-file` で読み込みます。`--env-file` は **`=` より後ろをすべて値として扱います**。値を引用符で囲んだり、値の後ろに `# コメント` を書いたりしないでください。

| 変数 | 設定する値と確認方法 |
| --- | --- |
| `CONSOLE_WEB_URL` | ブラウザで開く Dify の URL（例: `https://dify.example.com`）。末尾に `/` は付けません。ログイン後のリダイレクト先になります。`https` で始まると Cookie に Secure 属性と `__Host-` 付きの Cookie が追加されます（`app/services/token.py:17-23`） |
| `SECRET_KEY` | **Dify と同じ値**にします。`grep -E '^SECRET_KEY=' ${DIFY_DIR}/docker/.env` で確認できます。Dify の初期値のまま運用している場合は、Dify 側も含めて変更を検討してください |
| `TENANT_ID` | SSO ユーザーを参加させるワークスペースの ID。確認方法は下記 |
| `EDITION` | `SELF_HOSTED` のまま |
| `ACCOUNT_DEFAULT_ROLE` | 初めてワークスペースに参加するユーザーのロール。`normal`（メンバー）、`editor`（編集者）、`admin`（管理者）のどれか。無効な値の場合は `normal` になります（`app/services/oidc.py:129-130`）。`owner` も値としては受け付けますが、使わないでください |
| `ACCESS_TOKEN_EXPIRE_MINUTES` など、トークンに関する 4 項目 | `.env.example` の値のままで構いません。`REFRESH_TOKEN_PREFIX` と `ACCOUNT_REFRESH_TOKEN_PREFIX` は Dify 本体で固定の値（`refresh_token:`、`account_refresh_token:`）なので、変更しないでください |
| `TIMEZONE` | `Asia/Tokyo`（`.env.example` の値のまま） |
| `OIDC_*` | [A-5](#a-5-idp-の設定keycloak-の例) で確認します |
| `DB_USERNAME` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_DATABASE` | Dify の `.env` と同じ値にします: `grep -E '^DB_(USERNAME\|PASSWORD\|HOST\|PORT\|DATABASE)=' ${DIFY_DIR}/docker/.env`。`DB_HOST` には Dify の Compose のサービス名（例: `db_postgres`。古い Dify では `db`）を指定します |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` / `REDIS_PASSWORD` | Dify の `.env` と同じ値にします: `grep -E '^REDIS_(HOST\|PORT\|DB\|PASSWORD)=' ${DIFY_DIR}/docker/.env`。`REDIS_DB` も Dify と同じ番号にしてください。dify-sso が保存したリフレッシュトークンを、Dify 本体がトークン更新のときに同じ Redis から読むためです |
| `REDIS_SERIALIZATION_PROTOCOL` | `2` のまま |
| `APP_DSL_VERSION` | Dify の `api/constants/dsl_version.py` にある `CURRENT_APP_DSL_VERSION` の値 |
| `LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT` | Dify 1.13.x は `true`、1.14.0 以降は `false` |
| `SSO_ENFORCED_FOR_SIGNIN` | `true` にすると SSO ボタンが表示されます。`ENABLE_EMAIL_PASSWORD_LOGIN=true` のままなら、パスワードでのログインも使えます。導入中は、管理者が戻れるようにパスワードログインを残しておくと安全です |
| `DIFY_API_INTERNAL_URL` | 通常は `http://api:5001` のまま |

**`TENANT_ID` の調べ方**

```bash
docker ps --format '{{.Names}}' | grep -i postgres   # 例: docker-db_postgres-1
docker exec -it docker-db_postgres-1 psql -U postgres -d dify
```

```sql
SELECT id,name FROM tenants;
```

`name` が対象のワークスペースになっている行の `id`（UUID）を `TENANT_ID` に設定します。`-U` と `-d` には、Dify の `DB_USERNAME` と `DB_DATABASE` を指定してください。指定できるワークスペースは 1 つだけです。

### A-5. IdP の設定（Keycloak の例）

#### Keycloak のクライアントを作成する

1. 対象のレルムで **Clients** → **Create client** を開き、Client type に `OpenID Connect`、Client ID に任意の値（例: `dify`）を入力します。
2. **Client authentication を ON**（confidential client）にし、**Standard flow** を有効にします。
3. **Valid redirect URIs** に `https://dify.example.com/console/api/enterprise/sso/oidc/callback`（`{Dify の URL}/console/api/enterprise/sso/oidc/callback`）を登録します。
   - WebApp（公開アプリ）で SSO を使う場合、dify-sso は redirect_uri の後ろに `?app_code=...&redirect_url=...` を付けます（`app/services/oidc.py:65-67`）。Keycloak では、末尾に `*` を付けたワイルドカードで登録しないと一致しない可能性があります（**要確認**）。
4. **Credentials** タブに表示される Client secret を確認します。
5. `.env` を次のように設定します。

```dotenv
OIDC_CLIENT_ID=dify
OIDC_CLIENT_SECRET=<Credentials タブの Client secret>
OIDC_DISCOVERY_URL=https://keycloak.example.local/realms/myrealm/.well-known/openid-configuration
OIDC_REDIRECT_URI=https://dify.example.com/console/api/enterprise/sso/oidc/callback
OIDC_SCOPE=openid profile email roles
OIDC_RESPONSE_TYPE=code
```

- Discovery URL の形式は `https://<keycloak>/realms/<realm>/.well-known/openid-configuration` です（古い WildFly 版の Keycloak では `/auth/realms/...`）。
- dify-sso は**起動時に** discovery URL へアクセスします（`app/extensions/ext_oidc.py:5` → `app/services/oidc.py:34-47`）。ここに接続できないと起動に失敗します。
- discovery が返す `authorization_endpoint` にはブラウザがアクセスし、`token_endpoint` と `userinfo_endpoint` には dify-sso コンテナがアクセスします。Keycloak のホスト名は、**ブラウザからも dify-sso コンテナからも名前解決でき、接続できる**必要があります。

#### ロールを IdP から渡す場合（任意）

dify-sso は userinfo の**トップレベルにある `roles` 配列**だけを見ます（`app/services/oidc.py:112, 131-136`）。Keycloak は標準ではロールを `realm_access.roles` に入れるため、次のような設定が必要です（Keycloak のバージョンによって画面が違うので、**要確認**）。

1. レルムロール `admin`、`editor`、`normal` を作成して、ユーザーまたはグループに割り当てます。
2. クライアントの専用スコープ（`dify-dedicated`）で **Add mapper** → **By configuration** → **User Realm Role** を選び、Token Claim Name を `roles`、Multivalued を ON、**Add to userinfo を ON** にします。
3. `OIDC_SCOPE` には `roles` が含まれています（既定値）。Keycloak で `roles` スコープを削除している場合は、`OIDC_SCOPE` から `roles` を外してください。

ロールが反映されるのは、**そのユーザーが初めてワークスペースに参加したときだけ**です。それ以降の変更は Dify のメンバー管理画面で行ってください。

#### LDAP / Active Directory と連携する場合

dify-sso は LDAP に直接接続しません。Keycloak の **User Federation** で AD/LDAP を取り込み、Keycloak 経由で OIDC ログインさせます。

- **User Federation** → **Add LDAP providers** を開き、Vendor に `Active Directory` を選びます。接続 URL（例: `ldaps://ad.example.local:636`）、Bind DN とパスワード、Users DN を設定します。Username LDAP attribute は、多くの場合 `sAMAccountName` です。
- `mail` 属性が Keycloak の `email` にマッピングされていることを確認してください。メールアドレスのないユーザーは Dify にログインできません。
- AD のグループを Dify のロールにしたい場合は、LDAP の group / role マッパーでレルムロール（`admin` など）に対応付けます（**要確認**）。
- LDAPS のサーバー証明書が社内 CA で署名されている場合は、**Keycloak 側**の truststore に社内 CA を登録する必要があります（dify-sso の設定とは別です）。

#### Casdoor の場合

Casdoor では「アプリケーション」を作り、リダイレクト URL に同じコールバック URL を登録します。`OIDC_DISCOVERY_URL` には **Casdoor の URL** を使って `https://<casdoor>/.well-known/openid-configuration` を指定します。元の中国語 README の手順と画面例は [README_zh.md](README_zh.md) を参照してください。Casdoor の userinfo にどの形式で `roles` が入るかは**要確認**です。

### A-6. イメージのビルドとコンテナの起動

#### 方法 1: このフォークのソースからビルドする（推奨）

```bash
cd /opt/dify-ssoJ
docker build -t dify-ssoj:local .
```

`certs/` に `.crt` を置いていれば、ビルド時にイメージに組み込まれます（[B-3](#b-3-ビルド時にイメージへ組み込む方法推奨)）。

#### 方法 2: 公開イメージを使う（ビルドしない場合）

`ghcr.io/xjfyt/dify-sso:latest` は xjfyt 版（`a2b5bb5`）のイメージで、**このフォークの修正は入っていません**。リフレッシュトークンが約 30 秒で消える、`TIMEZONE=Asia/Tokyo` だと WebApp の SSO トークンが発行時点で期限切れになる、などの不具合が残っています。どうしてもビルドできない場合の一時的な手段と考えてください。社内 CA は [B-4](#b-4-ビルドせずにボリュームマウントで渡す方法) の方法で渡せます。

#### 起動

Dify の DB と Redis が参加している Docker ネットワークを確認します。

```bash
docker network ls
docker network inspect docker_default --format '{{range .Containers}}{{.Name}} {{end}}'
```

起動します（方法 2 の場合は、イメージ名を `ghcr.io/xjfyt/dify-sso:latest` にします）。

```bash
docker run -d \
  --name dify-sso \
  --hostname dify-sso \
  --restart always \
  --network docker_default \
  --env-file /opt/dify-ssoJ/.env \
  dify-ssoj:local
```

- Nginx はコンテナ名 `dify-sso` で接続するので、`-p 8000:8000` は必須ではありません。ホストから直接確認したいときだけ付けてください。
- Dify の `docker-compose.yaml` にまとめたい場合は `yaml/docker-compose.yaml` を参考にします。ただし中身はサンプル値なので、`.env` と同じ値に書き換えてください。
- 起動ログを確認します: `docker logs -f dify-sso`。`Failed to load OIDC configuration` や `CERTIFICATE_VERIFY_FAILED` が出ていないことを確認してください。

### A-7. Nginx の設定

Dify に同梱されている Nginx のテンプレートを編集します（`default.conf` ではなく **`default.conf.template`** を編集します。`default.conf` はコンテナの起動時にテンプレートから作り直されます）。

```bash
cd ${DIFY_DIR}/docker/nginx/conf.d
cp default.conf.template default.conf.template.bak
nano default.conf.template
```

`server { ... }` の中で、**`location /console/api` より上**に次の設定を追加します。

```nginx
    location ~ ^/console/api/system-features {
      proxy_pass http://dify-sso:8000;
      proxy_set_header X-Csrf-Token $http_x_csrf_token;
      include proxy.conf;
    }

    location ~ ^/console/api/enterprise/sso/ {
      proxy_pass http://dify-sso:8000;
      proxy_set_header X-Csrf-Token $http_x_csrf_token;
      include proxy.conf;
    }

    location ~ ^/console/api/enterprise/webapp/ {
      proxy_pass http://dify-sso:8000;
      proxy_set_header X-Csrf-Token $http_x_csrf_token;
      include proxy.conf;
    }

    location ~ ^/api/enterprise/ {
      proxy_pass http://dify-sso:8000;
      proxy_set_header X-Csrf-Token $http_x_csrf_token;
      include proxy.conf;
    }
```

dify-sso コンテナが起動していることを確認してから、Nginx を再起動します。`dify-sso` という名前を解決できないと、Nginx は起動に失敗します。

```bash
cd ${DIFY_DIR}/docker
docker compose restart nginx
docker compose logs --tail 50 nginx
```

Dify の前に別のリバースプロキシを置いている場合も、同じ 4 つのパスを dify-sso に振り分けてください。

### A-8. 動作確認

```bash
# 1) dify-sso 自体と DB / Redis への接続
docker exec dify-sso python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health?detail=1').read().decode())"
#    期待される結果: {"database":true,"redis":true,"status":"healthy"}

# 2) Nginx が dify-sso に振り分けているか
curl -s https://dify.example.com/console/api/system-features
#    JSON に "sso_enforced_for_signin":true と "license":{..."status":"active"...} が含まれていれば OK

# 3) IdP のログイン URL が生成されるか
curl -s https://dify.example.com/console/api/enterprise/sso/oidc/login
#    {"url": "https://keycloak.example.local/realms/myrealm/protocol/openid-connect/auth?..."} が返れば OK
```

4. ブラウザで Dify を開き、「SSO でログイン」から Keycloak でログインして、Dify の画面に戻ってくることを確認します。
5. `docker logs dify-sso` に `用户验证成功: <メールアドレス>, 角色: <ロール>` が出ること、Dify のメンバー一覧にユーザーが追加されていることを確認します。

---

## B. 社内 CA 証明書を使う場合

Keycloak などの IdP が**社内 CA で署名された TLS 証明書**を使っている場合、dify-sso から IdP への HTTPS 接続（discovery、token、userinfo）で証明書の検証に失敗します。dify-sso は起動時に discovery URL へ接続するので、そのままでは**起動できません**。

### B-1. 仕組み

| 箇所 | 内容 |
| --- | --- |
| `app/services/oidc.py:38, 84, 94` | IdP への通信は `requests` の `get` / `post` で行う。`verify=` は指定していない |
| `Dockerfile:24-27` | `REQUESTS_CA_BUNDLE` と `SSL_CERT_FILE` を `/etc/ssl/certs/ca-certificates.crt`（システムの証明書ストア）に設定する |
| `Dockerfile:30-34` | `ca-certificates` をインストールする |
| `Dockerfile:43` | `certs/` の中身を `/usr/local/share/ca-certificates/company/` にコピーする |
| `Dockerfile:46` | `update-ca-certificates` を実行する。`.crt` ファイルだけがシステムの証明書ストアに追加される（`.gitkeep` と `README.md` は無視される） |

`requests` は、`verify` を指定しないと **`REQUESTS_CA_BUNDLE` 環境変数のファイル**を CA バンドルとして使い、設定がなければ certifi に同梱されたバンドルを使います。**`SSL_CERT_FILE` だけでは requests には効きません。** 社内 CA を信頼させるには「社内 CA を含むバンドルを用意し、`REQUESTS_CA_BUNDLE` でそのファイルを指す」必要があります。方法は 2 つあります。

- **B-3. ビルド時に組み込む（推奨）**: `certs/` に置いてビルドする。イメージの `REQUESTS_CA_BUNDLE` がシステムの証明書ストアを指しているので、追加の設定はいらない
- **B-4. 実行時にマウントする**: ビルドせずに、バンドルファイルをマウントして `REQUESTS_CA_BUNDLE` で指定する

ローカルの Python 3.11 と requests 2.32.3 で、テスト用の社内 CA（ルート CA → 中間 CA → サーバー証明書）を使って次のことを確認しました。Debian bookworm の `update-ca-certificates` スクリプトで、ビルド時と同じ処理も再現しています。

| `certs/` の中身 | 結果 |
| --- | --- |
| `.crt` なし | `update-ca-certificates` はエラーなく完了する（バンドルは変わらない） |
| ルート CA だけ（サーバーが中間 CA を送らない場合） | `CERTIFICATE_VERIFY_FAILED` で起動に失敗する |
| ルート CA と中間 CA | 起動できる |
| （参考）`SSL_CERT_FILE` だけ設定し、`REQUESTS_CA_BUNDLE` を設定しない | `CERTIFICATE_VERIFY_FAILED` で起動に失敗する |

### B-2. 証明書の準備

- **形式**: PEM（`-----BEGIN CERTIFICATE-----` で始まるテキスト）。拡張子は **`.crt`** にします。`.crt` 以外（`.pem`、`.cer` など）は取り込まれません。
- **含める証明書**: 社内の**ルート CA** は必須です。IdP のサーバーが中間 CA の証明書を送っていない場合は、**中間 CA** も必要です（B-5 の `openssl s_client -showcerts` で確認できます）。ファイルは複数置けます。本来は、IdP 側で中間 CA を含むチェーン全体を送るように設定するのが望ましいです。
- **確認と変換**:

  ```bash
  openssl x509 -in company-root.crt -noout -subject -issuer -enddate   # PEM として読めるか、有効期限
  openssl x509 -inform DER -in rootca.cer -out company-root.crt        # DER 形式（バイナリ）なら PEM に変換
  ```

- **配置場所**: リポジトリの `certs/`（例: `/opt/dify-ssoJ/certs/company-root.crt`、`/opt/dify-ssoJ/certs/company-intermediate.crt`）。
- `certs/` の中は `.gitkeep` と `README.md` を除いて `.gitignore` で除外しています。これは公開リポジトリのフォークなので、`git add -f` などで**証明書をコミットしないでください**。なお `.gitignore` は Docker のビルドには影響しないので、`certs/` に置いた証明書はビルドに使われます。

### B-3. ビルド時にイメージへ組み込む方法（推奨）

```bash
cd /opt/dify-ssoJ
cp /path/to/company-root.crt /path/to/company-intermediate.crt certs/
docker build -t dify-ssoj:local .
docker rm -f dify-sso   # すでに起動している場合
# A-6 の docker run を実行する
```

組み込まれたことを確認します。

```bash
docker exec dify-sso sh -c 'echo $REQUESTS_CA_BUNDLE; ls -l /etc/ssl/certs/ | grep company'
# /etc/ssl/certs/ca-certificates.crt と、certs/ に置いたファイル名の .pem（例: company-root.pem）へのリンクが表示されれば OK
# （リンク先は /usr/local/share/ca-certificates/company/ 配下）
```

CA 証明書を追加・更新したときは、イメージをビルドし直してコンテナを作り直してください。

### B-4. ビルドせずにボリュームマウントで渡す方法

アプリは `REQUESTS_CA_BUNDLE` を実行時に参照するので、**社内 CA を含むバンドルをマウントし、`REQUESTS_CA_BUNDLE` でそのファイルを指定する**方法でも対応できます。`-e` で指定した値は、イメージの `ENV` より優先されます。B-1 の確認結果から動作するはずですが、実際のコンテナでは試していないので**要確認**です。

```bash
mkdir -p /opt/dify-sso-ca   # リポジトリの外に置く（誤コミット防止）
# ホストの公開 CA バンドル + 社内 CA（RHEL 系のホストでは /etc/pki/tls/certs/ca-bundle.crt）
cat /etc/ssl/certs/ca-certificates.crt /path/to/company-root.crt /path/to/company-intermediate.crt > /opt/dify-sso-ca/ca-bundle.crt

docker run -d \
  --name dify-sso --hostname dify-sso --restart always \
  --network docker_default \
  --env-file /opt/dify-ssoJ/.env \
  -e REQUESTS_CA_BUNDLE=/etc/dify-sso/ca-bundle.crt \
  -v /opt/dify-sso-ca/ca-bundle.crt:/etc/dify-sso/ca-bundle.crt:ro \
  dify-ssoj:local
```

- `REQUESTS_CA_BUNDLE` は `.env` に書いても構いません。
- 証明書を `/usr/local/share/ca-certificates/` にマウントするだけでは**反映されません**。起動時に `update-ca-certificates` は実行されないためです。
- 公開イメージ（`ghcr.io/xjfyt/dify-sso:latest`）でも同じ方法を使えますが、このフォークの修正は入っていません（A-6 の方法 2 を参照）。

### B-5. 接続の確認

```bash
# dify-sso コンテナから discovery URL に接続する
docker exec dify-sso python -c "import os, requests; print('REQUESTS_CA_BUNDLE =', os.environ.get('REQUESTS_CA_BUNDLE')); r = requests.get('https://keycloak.example.local/realms/myrealm/.well-known/openid-configuration', timeout=10); print(r.status_code, r.json()['issuer'])"
```

dify-sso が起動に失敗して再起動を繰り返している場合は、`docker exec` が使えません。同じイメージから一時的なコンテナを起動して確認します（コマンドを上書きするので、アプリは起動しません）。

```bash
docker run --rm --network docker_default dify-ssoj:local \
  python -c "import requests; print(requests.get('https://keycloak.example.local/realms/myrealm/.well-known/openid-configuration', timeout=10).status_code)"
```

サーバーが送ってくる証明書チェーンを確認します（ホストで実行します）。

```bash
openssl s_client -connect keycloak.example.local:443 -servername keycloak.example.local -showcerts </dev/null
# "Certificate chain" の s:（subject）と i:（issuer）で、中間 CA が送られているかを確認する

cat certs/*.crt > /tmp/company-ca.pem
openssl s_client -connect keycloak.example.local:443 -servername keycloak.example.local -CAfile /tmp/company-ca.pem </dev/null 2>/dev/null | grep 'Verify return code'
# "Verify return code: 0 (ok)" であれば、certs/ の証明書でチェーンを検証できている
```

### B-6. 対象範囲

この設定が影響するのは、**dify-sso コンテナから IdP への通信だけ**です。次の項目はそれぞれ別に対応してください。

- **ブラウザ**: ユーザーのブラウザは Keycloak に直接アクセスします。社内 CA を各 PC に配布して、信頼させてください。
- **Dify の Nginx の HTTPS 証明書**: Dify 側の設定です（`NGINX_HTTPS_ENABLED`、`docker/nginx/ssl` など）。
- **Dify 本体（api / worker / plugin_daemon など）から社内サーバーへの通信**: Dify の各コンテナで、別途 CA を設定する必要があります。
- **Keycloak から AD への LDAPS 接続**: Keycloak の truststore で設定します。

### B-7. よくあるエラーと対処

| エラー（`docker logs dify-sso` などに出るもの） | 主な原因 | 対処 |
| --- | --- | --- |
| `SSLError ... CERTIFICATE_VERIFY_FAILED ... unable to get local issuer certificate` | 社内 CA がバンドルに入っていない（`certs/` に置かずにビルドした、拡張子が `.crt` でない）。中間 CA が足りない。B-4 で `REQUESTS_CA_BUNDLE` を指定していない | B-3 または B-4 をやり直す。B-5 の `openssl s_client` でチェーンを確認し、必要なら中間 CA も追加する |
| `... self-signed certificate in certificate chain` | ルート CA が信頼されていない | `certs/` に置いた証明書がルート CA であることを、`-subject` と `-issuer` が同じかどうかで確認する |
| `... Hostname mismatch, certificate is not valid for '...'` | `OIDC_DISCOVERY_URL` のホスト名、または discovery が返すエンドポイントのホスト名が、証明書の SAN と一致しない | 証明書の SAN に含まれる FQDN で接続する。Keycloak のホスト名の設定を確認する |
| `... certificate has expired` | サーバー証明書または CA 証明書の期限切れ | `openssl x509 -enddate` で確認して更新する |
| `Could not find a suitable TLS CA certificate bundle, invalid path: ...` | `REQUESTS_CA_BUNDLE` で指定したファイルがコンテナ内にない | マウント先のパスと `-v` の指定を確認する |
| ビルド時の `"/certs": not found` | `certs/` ディレクトリがない（`.gitkeep` ごと削除した、など） | `mkdir certs` で作り直す（空で構わない） |
| `Failed to load OIDC configuration` | discovery URL が 200 を返さない（URL の誤り、レルム名の誤り、プロキシなど） | B-5 のコマンドで、ステータスコードとレスポンスを確認する |

> [!CAUTION]
> TLS 証明書の検証を無効にする方法（`verify=False` など）は、対処として使わないでください。dify-sso のコードにもそのような設定はありません。

---

## C. トラブルシューティング

| 症状 | 確認すること |
| --- | --- |
| Keycloak で `Invalid parameter: redirect_uri` が出る | `OIDC_REDIRECT_URI` と Keycloak の Valid redirect URIs が完全に一致しているか（`http` と `https` の違い、ホスト名、ポート、末尾の `/`）。WebApp の SSO ではクエリが付くので、A-5 の注意も確認する |
| Nginx が起動しない（`host not found in upstream "dify-sso"`） | dify-sso が起動しているか、Nginx と同じネットワーク（例: `docker_default`）に参加しているか。`docker network inspect docker_default` で確認する |
| `/health?detail=1` で `database` または `redis` が `false` になる | `--network` の指定、`DB_HOST` / `REDIS_HOST`（Compose のサービス名）、パスワード |
| ログイン後に Dify に戻るが、ログイン画面に戻される、または 401 になる | `SECRET_KEY` が Dify と同じか。`CONSOLE_WEB_URL` の `http` / `https` が実際のアクセスと一致しているか（Cookie の名前と Secure 属性が変わるため） |
| 操作すると CSRF のエラーになる | Nginx の 4 つの location に `proxy_set_header X-Csrf-Token $http_x_csrf_token;` があるか。CSRF トークンは dify-sso が `SECRET_KEY` で署名して発行しているので、`SECRET_KEY` が Dify と同じかも確認する（`app/services/token.py:29-36`） |
| `User email is required` で 400 エラーになる | IdP の userinfo に `email` がない。Keycloak ではユーザーにメールアドレスを設定し、`email` スコープとマッパーを確認する |
| ロールが期待どおりにならない | ロールが反映されるのは初めて参加したときだけ。既存メンバーは Dify の画面で変更する。`roles` が userinfo のトップレベルにあるか（一時的に `DEBUG=true` にすると `UserInfo:` のログが出る。トークンなどもログに出るので、確認が終わったら戻す）。`ACCOUNT_DEFAULT_ROLE` のつづり |
| ログインできるが、ワークスペースがない、またはエラーになる | `TENANT_ID` が `SELECT id,name FROM tenants;` の `id` と一致しているか（空白などが混じっていないか） |
| SSO ボタンが表示されない | `curl .../console/api/system-features` の結果が dify-sso のものか（Nginx の location の順番。`/console/api` より上にあるか）。`SSO_ENFORCED_FOR_SIGNIN=true` か。ブラウザのキャッシュ |
| 時刻がずれて見える | `TIMEZONE`（`.env.example` は `Asia/Shanghai`）を `Asia/Tokyo` にする。ログの時刻は `LOG_TZ`（既定値 `UTC`）で決まるので、日本時間で見たい場合は `LOG_TZ=Asia/Tokyo` にする。DB への接続は常に `timezone=UTC` で、ログイン日時は UTC で保存される（`app/configs/database_config.py:104`、`app/libs/helper.py:16-17`） |
| 約 1 時間後にログアウトされる、WebApp の SSO ログインがすぐ切れる | 公開イメージ（`ghcr.io/xjfyt/dify-sso:latest`）や上流の古いコードを使っていないか。リフレッシュトークンの有効期限と WebApp のトークンの `exp` の不具合は、このフォークで修正済み |
| 起動直後にコンテナが終了する、または再起動を繰り返す | `docker logs dify-sso` で、`OIDC配置不完整` / `Failed to load OIDC configuration`（discovery URL）、`CERTIFICATE_VERIFY_FAILED`（B 章）を確認する。上流のコード（`86b4f58`）を使っている場合は `IndentationError` で起動しない |

### アップデート時の注意

- **Dify のバージョンは固定してください。** アップデートは、検証環境で dify-sso と組み合わせて確認してから行い、DB もバックアップしてください。
- Dify をアップデートすると `docker/nginx/conf.d/default.conf.template` が上書きされることがあります。**A-7 の location が残っているか**を毎回確認してください。
- Dify のバージョンに合わせて `APP_DSL_VERSION` と `LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT` を見直してください。
- Dify の内部 API や DB スキーマ（`accounts`、`tenant_account_joins`、`sites`、`installed_apps`）が変わると、動かなくなる可能性があります。リリースノートを確認してください。
- dify-sso を更新するとき（`git pull` など）は、イメージをビルドし直してから `docker rm -f dify-sso` と `docker run` でコンテナを作り直します。`certs/` の証明書は Git の管理外なので、別の場所に clone し直した場合は置き直してください。
- 上流（lockdlock/dify-ssoJ）の変更を取り込むときは、このフォークの修正（README の「既知の問題と修正状況」）と競合していないか確認してください。
