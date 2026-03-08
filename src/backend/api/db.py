"""Single-file database setup and models for the hackathon MVP."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    inspect,
    text,
)
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
    __table_args__ = (
        UniqueConstraint("vendor_id", "vendor_tx_id", name="uq_vendor_vendor_tx"),
    )

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    vendor_tx_id = Column(String(128), nullable=False, index=True)
    user_wallet_address = Column(String(128), nullable=False, index=True)
    merchant_wallet_address = Column(String(128), nullable=False, index=True)
    # Hackathon-only shortcut: plaintext seeds are NOT production-safe.
    amount_xrp = Column(Float, nullable=False, default=0.0)
    interval_days = Column(Integer, nullable=False, default=30)
    interval_seconds = Column(Integer, nullable=False, default=30 * 24 * 60 * 60)
    status = Column(String(32), nullable=False, default="pending")
    request_status = Column(String(32), nullable=False, default="pending", index=True)
    contract_signature = Column(String(256), nullable=False)
    contract_hash = Column(String(128), nullable=False, index=True)
    contract_alg = Column(String(32), nullable=False, default="HMAC-SHA256")
    contract_version = Column(String(16), nullable=False, default="v1")
    approved_at = Column(DateTime, nullable=True)
    approved_by_username = Column(String(128), nullable=True)
    start_date = Column(DateTime, nullable=False)
    next_payment_date = Column(DateTime, nullable=False)
    last_tx_hash = Column(String(128), nullable=True)
    auto_renew = Column(Boolean, nullable=False, default=True)
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


class SubscriptionCycle(Base):
    __tablename__ = "subscription_cycles"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"), nullable=False, index=True)
    cycle_index = Column(Integer, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    status = Column(String(32), nullable=False, default="locked")
    escrow_amount_xrp = Column(Float, nullable=True)
    escrow_offer_sequence = Column(Integer, nullable=True)
    escrow_create_tx_hash = Column(String(128), nullable=True)
    escrow_finish_tx_hash = Column(String(128), nullable=True)
    escrow_cancel_tx_hash = Column(String(128), nullable=True)
    escrow_cancel_after = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(128), unique=True, nullable=False, index=True)
    wallet_address = Column(String(128), nullable=False, index=True, default="")
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    hashed_password = Column(String, nullable=True)


class UserWallet(Base):
    __tablename__ = "user_wallets"
    __table_args__ = (
        UniqueConstraint("user_profile_id", "wallet_id", name="uq_user_wallet_link"),
        UniqueConstraint("user_profile_id", "nickname", name="uq_user_wallet_nickname"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False, index=True)
    nickname = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True, index=True)
    vendor_code = Column(String(64), unique=True, nullable=False, index=True)
    display_name = Column(String(128), nullable=False)
    wallet_address = Column(String(128), nullable=False, index=True)
    # Hackathon-only shortcut: plaintext shared secrets are NOT production-safe.
    shared_secret = Column(String(256), nullable=False, unique=True, index=True)
    webhook_url = Column(String(512), nullable=True)
    vendor_photo_url = Column(String(512), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(String(4096), nullable=False)
    signature = Column(String(512), nullable=True)
    status = Column(String(32), nullable=False, default="queued")
    http_status = Column(Integer, nullable=True)
    error = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


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


class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False, index=True)
    username = Column(String(128), nullable=False, index=True)
    wallet_address = Column(String(128), nullable=False, index=True)
    title = Column(String(256), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    summary_total_subscription_xrp = Column(Float, nullable=False, default=0.0)
    summary_total_one_time_xrp = Column(Float, nullable=False, default=0.0)
    summary_total_spend_xrp = Column(Float, nullable=False, default=0.0)
    active_subscription_count = Column(Integer, nullable=False, default=0)
    payment_count = Column(Integer, nullable=False, default=0)
    subscription_event_count = Column(Integer, nullable=False, default=0)
    pinata_cid = Column(String(255), nullable=False, index=True)
    pinata_file_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _repair_legacy_schema_if_needed()


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
    return {row[1] for row in rows}


def _repair_legacy_schema_if_needed() -> None:
    """
    Hackathon-safe schema repair for local SQLite.
    If old tables are missing required columns from the current codebase,
    recreate those specific tables so the app can start without manual migration.
    """
    required_columns = {
        "subscriptions": {
            "vendor_id",
            "user_profile_id",
            "vendor_tx_id",
            "request_status",
            "contract_signature",
            "contract_hash",
            "contract_alg",
            "contract_version",
            "auto_renew",
            "interval_seconds",
        },
        "vendors": {"vendor_code", "display_name", "wallet_address", "shared_secret", "vendor_photo_url"},
        "user_profiles": {"username", "wallet_address"},
        "webhook_deliveries": {"vendor_id", "event_type", "payload", "status"},
        "subscription_cycles": {"subscription_id", "cycle_index", "period_start", "period_end"},
        "snapshots": {"user_profile_id", "username", "wallet_address", "pinata_cid"},
        "user_wallets": {"user_profile_id", "wallet_id", "nickname"},
    }

    with engine.begin() as conn:
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())

        for table_name, expected_cols in required_columns.items():
            if table_name not in existing_tables:
                continue
            current_cols = _table_columns(conn, table_name)
            if expected_cols.issubset(current_cols):
                continue

            if table_name == "vendors":
                if "vendor_photo_url" not in current_cols:
                    conn.execute(text("ALTER TABLE vendors ADD COLUMN vendor_photo_url VARCHAR(512)"))
                    current_cols = _table_columns(conn, table_name)
                if expected_cols.issubset(current_cols):
                    continue

            # Recreate only mismatched local tables (wallets/transactions are preserved).
            conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))

        Base.metadata.create_all(bind=conn)


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
