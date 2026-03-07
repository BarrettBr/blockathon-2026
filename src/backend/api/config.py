"""Central config for the EquiPay hackathon MVP."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "EquiPay")
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes"}

    SQLITE_URL: str = os.getenv("SQLITE_URL", "sqlite:///./equipay.db")

    XRPL_RPC_URL: str = os.getenv(
        "XRPL_RPC_URL",
        "https://s.altnet.rippletest.net:51234",
    )
    XRPL_NETWORK: str = os.getenv("XRPL_NETWORK", "testnet")
    RLUSD_CURRENCY: str = os.getenv("RLUSD_CURRENCY", "RLUSD")
    RLUSD_ISSUER: str = os.getenv("RLUSD_ISSUER", "")
    AUTO_FUND_NEW_WALLETS: bool = os.getenv("AUTO_FUND_NEW_WALLETS", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    HANDSHAKE_APPROVAL_DROPS: str = os.getenv("HANDSHAKE_APPROVAL_DROPS", "1")
    DASHBOARD_RECENT_LIMIT: int = int(os.getenv("DASHBOARD_RECENT_LIMIT", "10"))
    FAUCET_RETRIES: int = int(os.getenv("FAUCET_RETRIES", "2"))
    XRPL_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("XRPL_REQUEST_TIMEOUT_SECONDS", "20"))


settings = Settings()
