import os
import time

from flask import Flask

from app.configs import config


def init_app(app: Flask):
    os.environ["TZ"] = config.TIMEZONE
    # Windows 没有 tzset；非 Windows 环境会让 time/datetime 立即读到新时区
    if hasattr(time, "tzset"):
        time.tzset()
