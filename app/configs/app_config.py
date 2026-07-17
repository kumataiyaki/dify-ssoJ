from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    DEBUG: bool = Field(
        description="Enable debug mode for the application",
        default=False,
    )

    CONSOLE_WEB_URL: str = Field(
        description="Base URL for the console web interface,used for frontend references and CORS configuration",
        default="",
    )

    SECRET_KEY: str = Field(
        description="Secret key for secure session cookie signing."
                    "Make sure you are changing this key for your deployment with a strong key."
                    "Generate a strong key using `openssl rand -base64 42` or set via the `SECRET_KEY` environment variable.",
        default="",
    )

    TENANT_ID: str = Field(
        description="Tenant ID for the application workspace.",
        default="",
    )

    EDITION: str = Field(
        description="Deployment edition of the application (e.g., 'SELF_HOSTED', 'CLOUD')",
        default="SELF_HOSTED",
    )

    ACCOUNT_DEFAULT_ROLE: str = Field(
        description="Default role for new accounts.",
        default="normal",
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: PositiveInt = Field(
        description="Expiration time for access tokens in minutes",
        default=900,
    )

    REFRESH_TOKEN_EXPIRE_DAYS: PositiveInt = Field(
        description="Expiration time for refresh tokens in days",
        default=30,
    )

    REFRESH_TOKEN_PREFIX: str = Field(
        description="Prefix for refresh tokens",
        default="refresh_token:",
    )

    ACCOUNT_REFRESH_TOKEN_PREFIX: str = Field(
        description="Prefix for account refresh tokens",
        default="account_refresh_token:",
    )

    TIMEZONE: str = Field(
        description="服务时区，影响 datetime.now() 与日志时间戳。"
                    "需使用 IANA tz 名称，如 Asia/Shanghai / UTC / America/New_York。"
                    "Docker 镜像需包含 tzdata 才能生效。",
        default="Asia/Tokyo",
    )

    DIFY_API_INTERNAL_URL: str = Field(
        description="Dify api 容器在 docker 网络中的内部地址（用于 apps 接口反代注入 access_mode）。"
                    "默认 http://api:5001，与 Dify 官方 docker-compose 服务名一致。"
                    "若你的 api 服务名不同（例如外部部署、独立机器），改成对应可达地址。",
        default="http://api:5001",
    )
