# syntax=docker/dockerfile:1.7
# ---- ビルドステージ：uv公式イメージ（uvバイナリ同梱） ----
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 依存関係を先にインストールして、アプリ変更時に依存キャッシュを利用できるようにする
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ---- 実行ステージ：Python実行環境 + プロジェクトvenvのみ ----
FROM python:3.11-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    GUNICORN_WORKERS=2 \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# タイムゾーン情報とCA証明書をインストール
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tzdata \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

# 社内CA証明書を追加（任意）
# certs/ に置いた PEM 形式の *.crt（複数可）をシステムの証明書ストアに追加する。
# *.crt が 1 つもなくてもビルドできる（.gitkeep / README.md は update-ca-certificates が無視する）。
# requests は REQUESTS_CA_BUNDLE（上の ENV）でこのストアを参照する。
COPY certs/ /usr/local/share/ca-certificates/company/

# CA証明書ストアを更新
RUN update-ca-certificates

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn -w ${GUNICORN_WORKERS} -b 0.0.0.0:8000 app.main:app"]
