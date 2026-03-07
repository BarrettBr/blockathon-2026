"""Application settings for XRPL Financial Hub backend."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    APP_NAME: str = os.getenv("APP_NAME", "XRPL Financial Hub")
    API_V1_PREFIX: str = os.getenv("API_V1_PREFIX", "/api/v1")
    XRPL_RPC_URL: str = os.getenv(
        "XRPL_RPC_URL",
        "https://s.altnet.rippletest.net:51234",
    )
    SQLITE_DATABASE_URL: str = os.getenv(
        "SQLITE_DATABASE_URL",
        "sqlite:///./xrpl_financial_hub.db",
    )


settings = Settings()
