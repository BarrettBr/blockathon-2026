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
    use_escrow = Column(Integer, nullable=False, default=1)
    escrow_amount_xrp = Column(Float, nullable=True)
    escrow_offer_sequence = Column(Integer, nullable=True)
    escrow_create_tx_hash = Column(String(128), nullable=True)
    escrow_status = Column(String(32), nullable=False, default="not_started")
    escrow_cancel_after = Column(Integer, nullable=True)


class SpendingGuard(Base):
    __tablename__ = "spending_guards"

    id = Column(Integer, primary_key=True, index=True)
    user_wallet_address = Column(String(128), unique=True, index=True, nullable=False)
    currency = Column(String(16), nullable=False, default="RLUSD")
    monthly_limit = Column(Float, nullable=False, default=0.0)
    spent_this_month = Column(Float, nullable=False, default=0.0)
    month_key = Column(String(16), nullable=False, index=True)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class HistoryEvent(Base):
    __tablename__ = "history_events"

    id = Column(Integer, primary_key=True, index=True)
    user_wallet_address = Column(String(128), index=True, nullable=False)
    event_type = Column(String(64), nullable=False)
    tx_hash = Column(String(128), nullable=True)
    counterparty_address = Column(String(128), nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String(16), nullable=False, default="XRP")
    status = Column(String(32), nullable=False, default="recorded")
    note = Column(String(256), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
