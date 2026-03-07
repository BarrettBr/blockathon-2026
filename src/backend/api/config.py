"""Central config for hackathon backend.

Edit values here or via env vars while iterating quickly.

TODO:
- Add secret management support (vault/doppler/1password env sync).
- Add separate config profiles for local/dev/staging/prod.
"""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "XRPL Financial Hub")
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes"}

    SQLITE_URL: str = os.getenv("SQLITE_URL", "sqlite:///./xrpl_financial_hub.db")

    XRPL_RPC_URL: str = os.getenv(
        "XRPL_RPC_URL",
        "https://s.altnet.rippletest.net:51234",
    )
    XRPL_NETWORK: str = os.getenv("XRPL_NETWORK", "testnet")
    AUTO_FUND_NEW_WALLETS: bool = os.getenv("AUTO_FUND_NEW_WALLETS", "true").lower() in {
        "1",
        "true",
        "yes",
    }


settings = Settings()
