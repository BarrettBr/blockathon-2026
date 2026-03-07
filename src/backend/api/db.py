"""Single-file database setup and models for the hackathon MVP."""

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings


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
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    tx_hash = Column(String(128), unique=True, index=True, nullable=True)
    tx_type = Column(String(64), nullable=False, default="payment")
    from_address = Column(String(128), nullable=False)
    to_address = Column(String(128), nullable=False)
    amount_xrp = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="submitted")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_wallet_address = Column(String(128), nullable=False, index=True)
    merchant_wallet_address = Column(String(128), nullable=False, index=True)
    # Hackathon-only shortcut: plaintext seeds are NOT production-safe.
    user_seed = Column(String(256), nullable=False)
    amount_xrp = Column(Float, nullable=False, default=0.0)
    interval_days = Column(Integer, nullable=False, default=30)
    status = Column(String(32), nullable=False, default="active")
    start_date = Column(Date, nullable=False)
    next_payment_date = Column(Date, nullable=False)
    last_tx_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
