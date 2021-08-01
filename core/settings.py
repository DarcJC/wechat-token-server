from typing import Optional

from pydantic import BaseSettings, RedisDsn, conint


class Settings(BaseSettings):
    WECHAT_APPID: str
    WECHAT_SECRET: str
    SERVER_SECRET: str
    REDIS_DSN: Optional[RedisDsn] = "redis://localhost/1"
    EXPIRE_SECS: Optional[conint(ge=1)] = 3600
    SERVER_HOST: Optional[str] = "0.0.0.0"
    SERVER_PORT: Optional[int] = 8866

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
