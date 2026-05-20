# syntax=docker/dockerfile:1.7
# ---- 构建阶段：uv 官方镜像自带 uv 二进制 ----
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# 先装依赖，再装项目本身：业务代码改动时可命中依赖层缓存
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# ---- 运行阶段：只带 Python 解释器 + 项目 venv ----
FROM python:3.11-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    GUNICORN_WORKERS=2

# tzdata 让 time.tzset() 能读到 /usr/share/zoneinfo/<TZ>，否则非 UTC 时区会静默 fallback
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app /app

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn -w ${GUNICORN_WORKERS} -b 0.0.0.0:8000 app.main:app"]
