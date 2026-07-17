from pydantic import Field
from pydantic_settings import BaseSettings


class FeatureConfig(BaseSettings):
    """Frontend feature flag configuration for the Dify Console/WebApp via `system-features`."""

    # ---------- 版本对齐 ----------
    APP_DSL_VERSION: str = Field(
        description="对应 Dify 内部的 CURRENT_APP_DSL_VERSION，升级 Dify 后请同步更新。"
                    "参考 dify/api/constants/dsl_version.py。",
        default="0.6.0",
    )

    LEGACY_KNOWLEDGE_RATE_LIMIT_AS_OBJECT: bool = Field(
        description="兼容老版本 Dify。"
                    "Dify 1.14.0 起 /features 中 knowledge_rate_limit 改为 int；"
                    "1.13.x 仍是 {limit, subscription_plan} 对象。"
                    "1.13.x 用户置 true，1.14.0+ 用户保持 false。",
        default=False,
    )

    # ---------- 插件安装来源 ----------
    PLUGIN_ALLOW_ALL_SOURCES: bool = Field(
        description="是否允许从所有来源安装插件（市场 + GitHub + 本地）。"
                    "True 时前端会显示 GitHub 安装和本地安装入口；False 时仅允许市场安装。",
        default=True,
    )

    PLUGIN_INSTALLATION_SCOPE: str = Field(
        description="插件来源白名单范围，对应 Dify 的 plugin_installation_scope。"
                    "可选: none / official_only / official_and_specific_partners / all",
        default="all",
    )

    # ---------- 登录方式 ----------
    # Note: The field name `SSO_ENFORCED_FOR_SIGNIN` uses Dify's own naming convention. 
    #Despite containing "enforced", it actually indicates whether SSO is available as a login option.
    # When set to `true`, the SSO login button is displayed. When set to `false`, the SSO login button is hidden.
    # Whether password or verification code login is allowed is controlled independently by the `ENABLE_EMAIL_*` settings below.
    SSO_ENFORCED_FOR_SIGNIN: bool = Field(
        description="是否显示 SSO 登录按钮（控制台 + Webapp 共用）。"
                    "True 时显示，False 时隐藏。即便置 True，只要 ENABLE_EMAIL_PASSWORD_LOGIN "
                    "也为 True，邮箱密码登录会与 SSO 并存（带 OR 分隔线）。",
        default=True,
    )

    SSO_PROTOCOL: str = Field(
        description="SSO 协议，会写入 sso_enforced_for_signin_protocol。"
                    "目前 dify-sso 仅实现了 OIDC。",
        default="oidc",
    )

    ENABLE_EMAIL_PASSWORD_LOGIN: bool = Field(
        description="是否启用邮箱+密码登录。",
        default=True,
    )

    ENABLE_EMAIL_CODE_LOGIN: bool = Field(
        description="是否启用邮箱验证码登录。",
        default=False,
    )

    ENABLE_SOCIAL_OAUTH_LOGIN: bool = Field(
        description="是否启用社交账号 OAuth 登录（GitHub/Google 等）。",
        default=False,
    )

    IS_ALLOW_REGISTER: bool = Field(
        description="是否允许用户自助注册账号。",
        default=False,
    )

    IS_ALLOW_CREATE_WORKSPACE: bool = Field(
        description="是否允许用户创建新的工作区。",
        default=True,
    )

    # ---------- Webapp（终端用户应用）访问控制提示 ----------
    # Note: The following three fields do not control the visibility of the SSO button on the WebApp login page
    #  (this is controlled by `SSO_ENFORCED_FOR_SIGNIN`).
    # They are used only by the Dify Console's "App Access Control" module to display informational messages.
    WEBAPP_ALLOW_SSO: bool = Field(
        description="Webapp 应用层是否允许 SSO 登录（仅影响访问控制提示，不影响登录页 SSO 按钮）。",
        default=True,
    )

    WEBAPP_ALLOW_EMAIL_PASSWORD_LOGIN: bool = Field(
        description="Webapp 应用层是否允许邮箱+密码登录（仅影响访问控制提示）。",
        default=True,
    )

    WEBAPP_ALLOW_EMAIL_CODE_LOGIN: bool = Field(
        description="Webapp 应用层是否允许邮箱验证码登录（仅影响访问控制提示）。",
        default=False,
    )
