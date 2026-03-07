"""Single-file database setup and models for the hackathon MVP."""

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings


def utc_now() -> datetime:
    """Return current UTC timestamp as timezone-aware datetime."""
    return datetime.now(timezone.utc)


engine = create_engine(
    settings.SQLITE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    address = Column(String(128), unique=True, index=True, nullable=False)
    # Hackathon-only shortcut: plaintext seeds are NOT production-safe.
    seed = Column(String(256), nullable=True)
    network = Column(String(32), nullable=False, default=settings.XRPL_NETWORK)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    tx_hash = Column(String(128), unique=True, index=True, nullable=True)
    tx_type = Column(String(64), nullable=False, default="payment")
    from_address = Column(String(128), nullable=False)
    to_address = Column(String(128), nullable=False)
    amount_xrp = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="submitted")
    created_at = Column(DateTime, nullable=False, default=utc_now)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_wallet_address = Column(String(128), nullable=False, index=True)
    merchant_wallet_address = Column(String(128), nullable=False, index=True)
    # Hackathon-only shortcut: plaintext seeds are NOT production-safe.
    user_seed = Column(String(256), nullable=False)
    amount_xrp = Column(Float, nullable=False, default=0.0)
    interval_days = Column(Integer, nullable=False, default=30)
    status = Column(String(32), nullable=False, default="pending_handshake")
    terms_hash = Column(String(128), nullable=False, index=True)
    handshake_status = Column(String(32), nullable=False, default="pending")
    user_approval_tx_hash = Column(String(128), nullable=True)
    service_approval_tx_hash = Column(String(128), nullable=True)
    start_date = Column(Date, nullable=False)
    next_payment_date = Column(Date, nullable=False)
    last_tx_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
