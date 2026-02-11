from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from models import Account, Category, Group, Transaction, TransactionCategory
from services.taxonomy import is_protected_category_id


class InvalidAmountError(ValueError):
    pass


class InvalidSortError(ValueError):
    pass


class AmbiguousTaxonomyFilterError(ValueError):
    pass


class CategoryAssignmentConflictError(ValueError):
    pass


class CategoryAssignmentPersistenceError(RuntimeError):
    pass


@dataclass
class TransactionListFilters:
    start: date | None = None
    end: date | None = None
    account: str | None = None
    source_table: str | None = None
    description_contains: str | None = None
    amount: str | None = None
    amount_min: str | None = None
    amount_max: str | None = None
    group_id: int | None = None
    group_name: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    sort_by: str = "date"
    sort_dir: str = "asc"
    limit: int = 200
    offset: int = 0


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError) as e:
        raise InvalidAmountError(f"Invalid decimal amount: {value!r}") from e


async def list_transactions(session: AsyncSession, *, filters: TransactionListFilters) -> list[dict]:
    if (filters.group_id is not None or filters.group_name is not None) and (
        filters.category_id is not None or filters.category_name is not None
    ):
        raise AmbiguousTaxonomyFilterError(
            "Provide either group filter or category filter, not both"
        )
    if filters.sort_by != "date":
        raise InvalidSortError("sort_by must be 'date'")
    if filters.sort_dir not in {"asc", "desc"}:
        raise InvalidSortError("sort_dir must be 'asc' or 'desc'")

    q = (
        select(Transaction, Account, TransactionCategory, Category, Group)
        .join(Account, Transaction.account_id == Account.id)
        .outerjoin(TransactionCategory, TransactionCategory.txn_id == Transaction.id)
        .outerjoin(Category, Category.id == TransactionCategory.category_id)
        .outerjoin(Group, Group.id == Category.group_id)
    )

    if filters.account:
        q = q.where(Account.name == filters.account)
    if filters.start:
        q = q.where(Transaction.date >= filters.start)
    if filters.end:
        q = q.where(Transaction.date <= filters.end)
    if filters.source_table:
        q = q.where(Transaction.source_table == filters.source_table)

    if filters.description_contains:
        pattern = f"%{filters.description_contains.strip().lower()}%"
        q = q.where(func.lower(Transaction.description).like(pattern))

    if filters.amount is not None:
        q = q.where(Transaction.amount == parse_decimal(filters.amount))
    if filters.amount_min is not None:
        q = q.where(Transaction.amount >= parse_decimal(filters.amount_min))
    if filters.amount_max is not None:
        q = q.where(Transaction.amount <= parse_decimal(filters.amount_max))
    if filters.group_id is not None:
        q = q.where(Group.id == filters.group_id)
    if filters.group_name is not None:
        q = q.where(Group.name == filters.group_name)
    if filters.category_id is not None:
        q = q.where(Category.id == filters.category_id)
    if filters.category_name is not None:
        q = q.where(Category.name == filters.category_name)

    if filters.sort_dir == "desc":
        q = q.order_by(Transaction.date.desc(), Transaction.id.desc())
    else:
        q = q.order_by(Transaction.date.asc(), Transaction.id.asc())
    q = q.limit(filters.limit).offset(filters.offset)

    res = await session.execute(q)
    rows = res.all()

    return [
        {
            "id": tx.id,
            "account_id": tx.account_id,
            "account": acct.name,
            "date": tx.date.isoformat(),
            "description": tx.description,
            "amount": float(tx.amount) if isinstance(tx.amount, Decimal) else tx.amount,
            "source_table": tx.source_table,
            "source_file": tx.source_file,
            "source_row": tx.source_row,
            "ledger_snapshot_id": tx.ledger_snapshot_id,
            "group_id": grp.id if grp else None,
            "group_name": grp.name if grp else None,
            "category_id": cat.id if cat else None,
            "category_name": cat.name if cat else None,
            "category_report_class": cat.report_class if cat else None,
            "categorized_at": link.assigned_at.isoformat() + "Z" if link else None,
        }
        for (tx, acct, link, cat, grp) in rows
    ]


async def assign_transaction_category(
    session: AsyncSession,
    *,
    txn_id: int,
    category_id: int,
) -> tuple[bool, str]:
    txn_exists = (
        await session.execute(select(Transaction.id).where(Transaction.id == txn_id).limit(1))
    ).scalar_one_or_none()
    if txn_exists is None:
        raise LookupError(f"Transaction does not exist: {txn_id}")

    category_exists = (
        await session.execute(select(Category.id).where(Category.id == category_id).limit(1))
    ).scalar_one_or_none()
    if category_exists is None:
        raise LookupError(f"Category does not exist: {category_id}")

    if await is_protected_category_id(session, category_id):
        raise ValueError(f"Protected categories cannot be assigned manually: {category_id}")

    try:
        existing_link = (
            await session.execute(
                select(TransactionCategory)
                .where(TransactionCategory.txn_id == txn_id)
                .limit(1)
            )
        ).scalar_one_or_none()

        if existing_link is None:
            session.add(
                TransactionCategory(
                    txn_id=txn_id,
                    category_id=category_id,
                    assigned_at=datetime.utcnow(),
                )
            )
            created = True
            message = "Transaction category assigned"
        else:
            existing_link.category_id = category_id
            existing_link.assigned_at = datetime.utcnow()
            created = False
            message = "Transaction category updated"

        await session.commit()
        return created, message
    except IntegrityError as e:
        await session.rollback()
        raise CategoryAssignmentConflictError(f"Category assignment conflict: {e}") from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise CategoryAssignmentPersistenceError(f"Failed to assign transaction category: {e}") from e
