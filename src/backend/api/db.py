"""Single-file database setup and basic models.

TODO:
- Introduce Alembic migrations before schema starts changing frequently.
- Remove plaintext seed storage or encrypt it at rest.
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
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
    seed = Column(String(256), nullable=True)
    network = Column(String(32), nullable=False, default=settings.XRPL_NETWORK)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    tx_hash = Column(String(128), unique=True, index=True, nullable=True)
    source_address = Column(String(128), nullable=False)
    destination_address = Column(String(128), nullable=False)
    amount_xrp = Column(Float, nullable=False, default=0.0)
    status = Column(String(32), nullable=False, default="submitted")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    owner_address = Column(String(128), nullable=False, index=True)
    amount_xrp = Column(Float, nullable=False, default=0.0)
    interval = Column(String(32), nullable=False, default="monthly")
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
