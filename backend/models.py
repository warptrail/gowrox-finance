from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(20))  # debit | credit | etc

    ledger_snapshots: Mapped[list["LedgerSnapshot"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


class LedgerSnapshot(Base):
    __tablename__ = "ledger_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
    )

    ledger_filename: Mapped[str] = mapped_column(String(255))
    ledger_sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    tx_min_date: Mapped[date] = mapped_column(Date)
    tx_max_date: Mapped[date] = mapped_column(Date)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    account: Mapped["Account"] = relationship(back_populates="ledger_snapshots")

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="ledger_snapshot",
        cascade="all, delete-orphan",
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
    )

    ledger_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("ledger_snapshots.id", ondelete="CASCADE"),
        index=True,
    )

    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(500))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    source_table: Mapped[str] = mapped_column(String(100))
    source_file: Mapped[str] = mapped_column(String(200))
    source_row: Mapped[int] = mapped_column(Integer)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    ledger_snapshot: Mapped["LedgerSnapshot"] = relationship(back_populates="transactions")


Index(
    "ix_transactions_account_date",
    Transaction.account_id,
    Transaction.date,
)
