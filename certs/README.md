# certs/（社内 CA 証明書の置き場所）

社内 CA で署名された IdP（Keycloak など）に HTTPS で接続する場合は、社内 CA の証明書をこのディレクトリに置いてから `docker build` してください。

- 形式は **PEM**（`-----BEGIN CERTIFICATE-----` で始まるテキスト）、拡張子は **`.crt`** にしてください。`.crt` 以外のファイルは取り込まれません。
- ルート CA は必須です。IdP のサーバーが中間 CA を送っていない場合は、中間 CA も置いてください。複数のファイルを置けます（例: `company-root.crt`、`company-intermediate.crt`）。
- ビルド時に `/usr/local/share/ca-certificates/company/` にコピーされ、`update-ca-certificates` でシステムの証明書ストア（`/etc/ssl/certs/ca-certificates.crt`）に追加されます。dify-sso は `REQUESTS_CA_BUNDLE` でこのストアを参照します。
- 証明書を置かなくてもビルドできます。
- このディレクトリの `.gitkeep` と `README.md` 以外は `.gitignore` で除外しています。社内の証明書をコミットしないでください。

詳しくは [docs/SETUP_ja.md の B 章](../docs/SETUP_ja.md#b-社内-ca-証明書を使う場合) を参照してください。
