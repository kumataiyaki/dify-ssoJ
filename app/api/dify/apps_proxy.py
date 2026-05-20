"""反向代理 Dify 的 /console/api/apps* 接口，给响应注入 access_mode。

背景
----
dify-sso 把 /console/api/system-features 里的 webapp_auth.enabled mock 成 True，
让前端走"企业版 WebApp Auth"渲染路径。但 Dify 后端只在自身 ENTERPRISE_ENABLED=true
时才会通过 EnterpriseService 把 access_mode 写进 app 响应；
用户实际场景里 ENTERPRISE_ENABLED 没开（默认），后端返回 access_mode=null。

Dify 1.14.1 web 端 app-card-sections.tsx:305 直接用 ACCESS_MODE_ICON_MAP[access_mode]
查表后渲染，access_mode=null 时 Icon=undefined，触发 React #130 —— 表现为打开应用
配置面板时整页崩成"渲染此组件时发生了意外错误"。

修复：把 /console/api/apps 与 /console/api/apps/<id>(/copy) 反代经过本服务，
在 JSON 响应里给 app 对象补一个 access_mode="public"（社区版本来就是全员可见）。
"""

import json
import logging

import requests
from flask import Response, request

from app.api.router import api
from app.configs import config

logger = logging.getLogger(__name__)

# Dify 社区版应用本就是 public，注入此值与实际语义一致。
DEFAULT_ACCESS_MODE = "public"

# RFC 7230 hop-by-hop 头：不能跨代理转发。
_HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

# 这些头由 requests / Flask 自己管，不要手动复制，避免长度对不上或重复压缩。
_SKIP_REQUEST_HEADERS = _HOP_BY_HOP | {"host", "content-length"}
_SKIP_RESPONSE_HEADERS = _HOP_BY_HOP | {"content-length", "content-encoding"}


def _upstream(path: str) -> str:
    return f"{config.DIFY_API_INTERNAL_URL.rstrip('/')}/console/api{path}"


def _forward_request_headers() -> dict:
    return {k: v for k, v in request.headers.items() if k.lower() not in _SKIP_REQUEST_HEADERS}


def _inject_access_mode(payload):
    """对响应中识别为 app 的 dict 注入 access_mode，原地修改。"""
    if not isinstance(payload, dict):
        return payload

    # 单个 app 对象：detail / copy / create 返回顶层即 app
    if "id" in payload and "mode" in payload and not payload.get("access_mode"):
        payload["access_mode"] = DEFAULT_ACCESS_MODE

    # 分页：{page, limit, total, has_more, data:[...]}
    items = payload.get("data")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and "id" in item and "mode" in item and not item.get("access_mode"):
                item["access_mode"] = DEFAULT_ACCESS_MODE

    return payload


def _proxy(upstream_path: str) -> Response:
    url = _upstream(upstream_path)
    method = request.method

    try:
        upstream = requests.request(
            method=method,
            url=url,
            params=list(request.args.items(multi=True)),
            data=request.get_data() if method in ("POST", "PUT", "PATCH", "DELETE") else None,
            headers=_forward_request_headers(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=60,
        )
    except requests.RequestException as e:
        logger.exception("apps_proxy upstream error: %s %s", method, url)
        return Response(
            json.dumps({"error": "upstream_unreachable", "message": str(e)}),
            status=502,
            mimetype="application/json",
        )

    content_type = upstream.headers.get("Content-Type", "")
    body = upstream.content

    # 仅在 JSON 响应上注入；其它响应原样回传
    if "application/json" in content_type:
        try:
            payload = upstream.json()
            _inject_access_mode(payload)
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        except ValueError:
            logger.warning("apps_proxy: upstream claimed JSON but body not parseable, passthrough")

    resp = Response(body, status=upstream.status_code, content_type=content_type or "application/octet-stream")
    for k, v in upstream.headers.items():
        if k.lower() in _SKIP_RESPONSE_HEADERS or k.lower() == "content-type":
            continue
        resp.headers[k] = v
    return resp


# ---- routes ---------------------------------------------------------------
# 只代理那些响应里**会带 access_mode 字段**的端点（参考 dify 1.14.1
# api/fields/app_fields.py 中含 access_mode 的三个 fields 定义）。其它子路径
# （/site、/api-enable、/export 等）继续走 nginx 直连 dify api，零侵入。


@api.route("/console/api/apps", methods=["GET", "POST"])
def proxy_apps_collection():
    return _proxy("/apps")


@api.route("/console/api/apps/<uuid:app_id>", methods=["GET", "PUT", "DELETE"])
def proxy_apps_detail(app_id):
    return _proxy(f"/apps/{app_id}")


@api.route("/console/api/apps/<uuid:app_id>/copy", methods=["POST"])
def proxy_apps_copy(app_id):
    return _proxy(f"/apps/{app_id}/copy")
