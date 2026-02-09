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
    Boolean,
    Text
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

# --- Classification overlay (v1) ---------------------------------------------

class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"),
        index=True,
    )

    name: Mapped[str] = mapped_column(String(120), index=True)

    # Drives analytics behavior:
    # - "auto": normal behavior (amount<0 counts as spending, amount>0 counts as income)
    # - "transfer": exclude from spend/income reports
    report_class: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)

    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    group: Mapped["Group"] = relationship(back_populates="categories")
    txn_links: Mapped[list["TransactionCategory"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("group_id", "name", name="uq_categories_group_name"),
    )


class TransactionCategory(Base):
    """
    1:1 assignment: each Transaction gets exactly one Category.
    (Enforced by txn_id being PK.)
    """
    __tablename__ = "transaction_categories"

    txn_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    txn: Mapped["Transaction"] = relationship()
    category: Mapped["Category"] = relationship(back_populates="txn_links")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)


class TransactionTag(Base):
    __tablename__ = "transaction_tags"

    txn_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    txn: Mapped["Transaction"] = relationship()
    tag: Mapped["Tag"] = relationship()


class TransactionNote(Base):
    __tablename__ = "transaction_notes"

    txn_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    note: Mapped[str] = mapped_column(Text, default="", nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    txn: Mapped["Transaction"] = relationship()


# Helpful indexes for filtering / joins
Index("ix_txn_categories_category_id", TransactionCategory.category_id)
Index("ix_txn_tags_tag_id", TransactionTag.tag_id)
