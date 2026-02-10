from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models import (
    Account,
    Transaction,
    TransactionCategory,
    Category,
    Group,
)

router = APIRouter(prefix="/api", tags=["transactions"])


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid decimal amount: {value!r}")


@router.get("/transactions")
async def list_transactions(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    account: Optional[str] = Query(default=None),
    source_table: Optional[str] = Query(default=None),
    description_contains: Optional[str] = Query(default=None),
    amount: Optional[str] = Query(default=None, description="Exact amount match, e.g. -19.99 or 19.99"),
    amount_min: Optional[str] = Query(default=None, description="Minimum amount (inclusive)"),
    amount_max: Optional[str] = Query(default=None, description="Maximum amount (inclusive)"),
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    # Select Transaction + joined classification overlay
    q = (
        select(Transaction, Account, TransactionCategory, Category, Group)
        .join(Account, Transaction.account_id == Account.id)
        .outerjoin(TransactionCategory, TransactionCategory.txn_id == Transaction.id)
        .outerjoin(Category, Category.id == TransactionCategory.category_id)
        .outerjoin(Group, Group.id == Category.group_id)
    )

    if account:
        q = q.where(Account.name == account)
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)
    if source_table:
        q = q.where(Transaction.source_table == source_table)

    if description_contains:
        pattern = f"%{description_contains.strip().lower()}%"
        q = q.where(func.lower(Transaction.description).like(pattern))

    if amount is not None:
        q = q.where(Transaction.amount == parse_decimal(amount))
    if amount_min is not None:
        q = q.where(Transaction.amount >= parse_decimal(amount_min))
    if amount_max is not None:
        q = q.where(Transaction.amount <= parse_decimal(amount_max))

    q = q.order_by(Transaction.date.asc(), Transaction.id.asc())
    q = q.limit(limit).offset(offset)

    res = await session.execute(q)
    rows = res.all()

    return [
        {
            "id": tx.id,
            "account_id": tx.account_id,
            "account": acct.name,  # convenience for the UI
            "date": tx.date.isoformat(),
            "description": tx.description,
            "amount": float(tx.amount) if isinstance(tx.amount, Decimal) else tx.amount,
            "source_table": tx.source_table,
            "source_file": tx.source_file,
            "source_row": tx.source_row,
            "ledger_snapshot_id": tx.ledger_snapshot_id,

            # Classification overlay (may be None if DB is in partial state)
            "group_id": grp.id if grp else None,
            "group_name": grp.name if grp else None,
            "category_id": cat.id if cat else None,
            "category_name": cat.name if cat else None,
            "category_report_class": cat.report_class if cat else None,
            "categorized_at": link.assigned_at.isoformat() + "Z" if link else None,
        }
        for (tx, acct, link, cat, grp) in rows
    ]