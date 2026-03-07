"""Central config for the EquiPay hackathon MVP."""

from dataclasses import dataclass
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
if load_dotenv:
    load_dotenv(dotenv_path=BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "EquiPay")
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")

    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes"}
    CORS_ALLOW_ORIGINS: str = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
    )

    SQLITE_URL: str = os.getenv("SQLITE_URL", "sqlite:///./equipay.db")

    XRPL_RPC_URL: str = os.getenv(
        "XRPL_RPC_URL",
        "https://s.devnet.rippletest.net:51234",
    )
    XRPL_NETWORK: str = os.getenv("XRPL_NETWORK", "devnet")
    XRPL_FAUCET_URL: str = os.getenv("XRPL_FAUCET_URL", "https://faucet.devnet.rippletest.net")
    RLUSD_CURRENCY: str = os.getenv("RLUSD_CURRENCY", "RLUSD")
    RLUSD_ISSUER: str = os.getenv("RLUSD_ISSUER", "")
    RLUSD_ISSUER_SEED: str = os.getenv("RLUSD_ISSUER_SEED", "")
    OPERATOR_WALLET_ADDRESS: str = os.getenv("OPERATOR_WALLET_ADDRESS", "")
    OPERATOR_WALLET_SEED: str = os.getenv("OPERATOR_WALLET_SEED", "")
    AUTO_FUND_NEW_WALLETS: bool = os.getenv("AUTO_FUND_NEW_WALLETS", "true").lower() in {
        "1",
        "true",
        "yes",
    }
    HANDSHAKE_APPROVAL_DROPS: str = os.getenv("HANDSHAKE_APPROVAL_DROPS", "1")
    VENDOR_SHARED_SECRET_HEADER: str = os.getenv("VENDOR_SHARED_SECRET_HEADER", "X-Vendor-Secret")
    WEBHOOK_SIGNATURE_HEADER: str = os.getenv("WEBHOOK_SIGNATURE_HEADER", "X-Equipay-Signature")
    WEBHOOK_TIMEOUT_SECONDS: int = int(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "10"))
    DASHBOARD_RECENT_LIMIT: int = int(os.getenv("DASHBOARD_RECENT_LIMIT", "10"))
    FAUCET_RETRIES: int = int(os.getenv("FAUCET_RETRIES", "2"))
    XRPL_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("XRPL_REQUEST_TIMEOUT_SECONDS", "20"))

    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    PINATA_JWT: str = os.getenv("PINATA_JWT", "")
    PINATA_UPLOAD_URL: str = os.getenv("PINATA_UPLOAD_URL", "https://api.pinata.cloud/pinning/pinJSONToIPFS")
    PINATA_GATEWAY_BASE_URL: str = os.getenv("PINATA_GATEWAY_BASE_URL", "https://gateway.pinata.cloud/ipfs")
    PINATA_TIMEOUT_SECONDS: int = int(os.getenv("PINATA_TIMEOUT_SECONDS", "20"))
    SNAPSHOT_DEFAULT_DAYS: int = int(os.getenv("SNAPSHOT_DEFAULT_DAYS", "30"))

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    GEMINI_API_BASE_URL: str = os.getenv("GEMINI_API_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")


settings = Settings()
