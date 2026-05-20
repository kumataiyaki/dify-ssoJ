from datetime import datetime, timedelta

from flask import request

from app.api.router import api
from app.configs import config

# ---------------------------------------------------------------------------
# Mock schema 版本对齐标记
# 本文件中的 mock 数据按 Dify 1.14.0 的 schema 对齐，并向下兼容 1.13.x。
# 参考来源：
#   dify/api/services/feature_service.py:124-182 (FeatureModel / SystemFeatureModel)
#   dify/api/services/billing_service.py:104-127 (BillingInfo)
#   dify/api/services/enterprise/enterprise_service.py (EnterpriseService.get_info)
#
# 兼容策略：
#   - 1.14.0 新增字段：直接补齐，1.13.x 前端会忽略未知字段
#   - 字段类型变化字段：通过 env 切换（如 LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT）
#   - 1.13.x 仍在用的旧字段（如 knowledge_rate_limit.subscription_plan）：保留，
#     1.14.0 的 TypedDict 会自动剔除
# ---------------------------------------------------------------------------
DIFY_SCHEMA_VERSION = "1.14.0 (compatible with 1.13.x+)"

# 不限额度：用一个足够大的常量替代 0，避免 Dify 前端把 0 当作"上限到了"。
UNLIMITED_QUOTA = 999999

# 许可证模拟有效期：100 年，避免 30 天后频繁过期。
LICENSE_VALID_DAYS = 365 * 100


def _license_expired_at() -> str:
    return (datetime.now() + timedelta(days=LICENSE_VALID_DAYS)).strftime("%Y-%m-%d")


# 模拟企业信息（当前未挂接口，保留供需要时启用）
MOCK_ENTERPRISE_INFO = {
    "sso_enforced_for_signin": True,
    "sso_enforced_for_signin_protocol": "oidc",
    "sso_enforced_for_web": True,
    "sso_enforced_for_web_protocol": "oidc",
    "enable_web_sso_switch_component": True,
    "enable_email_code_login": True,
    "enable_email_password_login": True,
    "is_allow_register": True,
    "is_allow_create_workspace": True,
    "license": {
        "status": "active",
        "expired_at": _license_expired_at()
    }
}

# 模拟计费信息（GET /subscription/info）
# 字段对齐 Dify 1.14.0 的 BillingInfo
# （dify/api/services/billing_service.py:104-127）
MOCK_BILLING_INFO = {
    "enabled": True,
    "subscription": {
        "plan": "enterprise",
        "interval": "year",
        # 1.14.0 新增字段
        "education": False
    },
    "members": {
        "size": 1,
        "limit": UNLIMITED_QUOTA
    },
    "apps": {
        "size": 1,
        "limit": UNLIMITED_QUOTA
    },
    "vector_space": {
        "size": 1,
        "limit": UNLIMITED_QUOTA
    },
    "documents_upload_quota": {
        "size": 1,
        "limit": UNLIMITED_QUOTA
    },
    "annotation_quota_limit": {
        "size": 1,
        "limit": UNLIMITED_QUOTA
    },
    "docs_processing": "top-priority",
    "can_replace_logo": True,
    # 社区版没有此能力，置 False 避免界面出现误导项
    "model_load_balancing_enabled": False,
    "dataset_operator_enabled": True,
    # billing_service.py _KnowledgeRateLimit (1.14.0): {size?, limit}
    # 1.14.0 TypedDict 会自动剔除 subscription_plan；保留它是为了兼容 1.13.x 前端读取
    "knowledge_rate_limit": {
        "limit": 200000,
        "subscription_plan": "enterprise"
    },
    # 1.14.0 新增字段
    "knowledge_pipeline_publish_enabled": True,
    "next_credit_reset_date": 0
}


def _build_system_features():
    """根据 FeatureConfig 动态构建 system-features 响应。

    字段对齐 Dify 1.14.0 的 SystemFeatureModel
    （dify/api/services/feature_service.py:160-182）。
    """
    return {
        "app_dsl_version": config.APP_DSL_VERSION,
        "sso_enforced_for_signin": config.SSO_ENFORCED_FOR_SIGNIN,
        "sso_enforced_for_signin_protocol": config.SSO_PROTOCOL if config.SSO_ENFORCED_FOR_SIGNIN else "",
        "enable_marketplace": True,
        "max_plugin_package_size": 52428800,
        "enable_email_code_login": config.ENABLE_EMAIL_CODE_LOGIN,
        "enable_email_password_login": config.ENABLE_EMAIL_PASSWORD_LOGIN,
        "enable_social_oauth_login": config.ENABLE_SOCIAL_OAUTH_LOGIN,
        "enable_collaboration_mode": False,
        "is_allow_register": config.IS_ALLOW_REGISTER,
        "is_allow_create_workspace": config.IS_ALLOW_CREATE_WORKSPACE,
        "is_email_setup": True,
        "license": {
            "status": "active",
            "expired_at": _license_expired_at(),
            "workspaces": {
                "enabled": True,
                "size": 1,
                "limit": UNLIMITED_QUOTA
            }
        },
        "branding": {
            "enabled": False,
            "application_title": "",
            "login_page_logo": "",
            "workspace_logo": "",
            "favicon": ""
        },
        "webapp_auth": {
            "enabled": True,
            "allow_sso": config.WEBAPP_ALLOW_SSO,
            "sso_config": {
                "protocol": "oidc",
            },
            "allow_email_code_login": config.WEBAPP_ALLOW_EMAIL_CODE_LOGIN,
            "allow_email_password_login": config.WEBAPP_ALLOW_EMAIL_PASSWORD_LOGIN
        },
        "plugin_installation_permission": {
            "plugin_installation_scope": config.PLUGIN_INSTALLATION_SCOPE,
            "restrict_to_marketplace_only": not config.PLUGIN_ALLOW_ALL_SOURCES
        },
        "enable_change_email": True,
        # 模拟企业版开启插件管理（Dify 在 ENTERPRISE_ENABLED 时会设 plugin_manager.enabled=True）
        "plugin_manager": {"enabled": True},
        "trial_models": [],
        "enable_creators_platform": False,
        "enable_trial_app": False,
        "enable_explore_banner": False
    }


def _build_features():
    """根据 FeatureConfig 动态构建 /console/api/features 响应。

    字段对齐 Dify 1.14.0 的 FeatureModel
    （dify/api/services/feature_service.py:124-147）。
    1.13.x 与 1.14.0 之间 knowledge_rate_limit 字段类型变化，
    由 LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT 控制。
    """
    # 1.13.x: object {limit, subscription_plan}；1.14.0+: int
    if config.LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT:
        knowledge_rate_limit_value = {
            "limit": 200000,
            "subscription_plan": "enterprise"
        }
    else:
        knowledge_rate_limit_value = 200000

    return {
        "billing": {
            "enabled": False,
            "subscription": {
                "plan": "enterprise",
                "interval": "year"
            }
        },
        "education": {
            "enabled": False,
            "activated": False
        },
        "members": {
            "size": 1,
            "limit": UNLIMITED_QUOTA
        },
        "apps": {
            "size": 1,
            "limit": UNLIMITED_QUOTA
        },
        "vector_space": {
            "size": 1,
            "limit": UNLIMITED_QUOTA
        },
        "knowledge_rate_limit": knowledge_rate_limit_value,
        "annotation_quota_limit": {
            "size": 1,
            "limit": UNLIMITED_QUOTA
        },
        "documents_upload_quota": {
            "size": 1,
            "limit": UNLIMITED_QUOTA
        },
        "docs_processing": "top-priority",
        "can_replace_logo": True,
        # 社区版没有此能力
        "model_load_balancing_enabled": False,
        "dataset_operator_enabled": True,
        "webapp_copyright_enabled": True,
        "workspace_members": {
            "enabled": True,
            "size": 1,
            "limit": UNLIMITED_QUOTA
        },
        "is_allow_transfer_workspace": True,
        # 以下为 1.14.0 新增字段（feature_service.py:140-147）
        # 1.13.x 前端会忽略未知字段，无副作用
        "trigger_event": {
            "usage": 0,
            "limit": UNLIMITED_QUOTA,
            "reset_date": 0
        },
        "api_rate_limit": {
            "usage": 0,
            "limit": UNLIMITED_QUOTA,
            "reset_date": 0
        },
        # Dify 在 ENTERPRISE_ENABLED 或非 BILLING_ENABLED 时返回 True (feature_service.py:218-226)
        "human_input_email_delivery_enabled": True,
        # Dify 在 ENTERPRISE_ENABLED 时会设 publish_enabled=True (feature_service.py:197)
        "knowledge_pipeline": {
            "publish_enabled": True
        },
        "next_credit_reset_date": 0
    }


# @api.get("/info")
# def get_enterprise_info():
#     return MOCK_ENTERPRISE_INFO


@api.get("/app-sso-setting")
def get_app_sso_setting():
    app_code = request.args.get("app_code", "")

    return {
        "enabled": True,
        "protocol": "oidc",
        "app_code": app_code
    }


# 计费相关接口
@api.get("/subscription/info")
def get_billing_info():
    return MOCK_BILLING_INFO


# 系统功能
@api.get("/console/api/system-features")
def get_system_features():
    return _build_system_features()


@api.get("/console/api/features")
def get_features():
    return _build_features()


# Mock 健康检查：方便排查 dify-sso 是否漏字段
@api.get("/console/api/_mock_health")
def mock_health():
    system_features = _build_system_features()
    features = _build_features()
    return {
        "dify_schema_version": DIFY_SCHEMA_VERSION,
        "fields": {
            "system_features": list(system_features.keys()),
            "features": list(features.keys()),
            "billing_info": list(MOCK_BILLING_INFO.keys()),
            "enterprise_info": list(MOCK_ENTERPRISE_INFO.keys()),
        },
        "feature_flags": {
            "APP_DSL_VERSION": config.APP_DSL_VERSION,
            "LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT": config.LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT,
            "PLUGIN_ALLOW_ALL_SOURCES": config.PLUGIN_ALLOW_ALL_SOURCES,
            "PLUGIN_INSTALLATION_SCOPE": config.PLUGIN_INSTALLATION_SCOPE,
            "SSO_ENFORCED_FOR_SIGNIN": config.SSO_ENFORCED_FOR_SIGNIN,
            "SSO_PROTOCOL": config.SSO_PROTOCOL,
            "ENABLE_EMAIL_PASSWORD_LOGIN": config.ENABLE_EMAIL_PASSWORD_LOGIN,
            "ENABLE_EMAIL_CODE_LOGIN": config.ENABLE_EMAIL_CODE_LOGIN,
            "ENABLE_SOCIAL_OAUTH_LOGIN": config.ENABLE_SOCIAL_OAUTH_LOGIN,
            "IS_ALLOW_REGISTER": config.IS_ALLOW_REGISTER,
            "IS_ALLOW_CREATE_WORKSPACE": config.IS_ALLOW_CREATE_WORKSPACE,
            "WEBAPP_ALLOW_SSO": config.WEBAPP_ALLOW_SSO,
            "WEBAPP_ALLOW_EMAIL_PASSWORD_LOGIN": config.WEBAPP_ALLOW_EMAIL_PASSWORD_LOGIN,
            "WEBAPP_ALLOW_EMAIL_CODE_LOGIN": config.WEBAPP_ALLOW_EMAIL_CODE_LOGIN,
            "DIFY_API_INTERNAL_URL": config.DIFY_API_INTERNAL_URL,
        },
        "proxies": {
            "/console/api/apps": "→ inject access_mode (fix for Dify 1.14.1 React #130)",
            "/console/api/apps/<uuid>": "→ inject access_mode",
            "/console/api/apps/<uuid>/copy": "→ inject access_mode",
        }
    }
