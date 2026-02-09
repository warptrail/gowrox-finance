from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models import Account, Transaction

router = APIRouter(prefix="/api", tags=["analytics"])


def parse_decimal(value: str) -> Decimal:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, AttributeError):
        raise HTTPException(status_code=400, detail=f"Invalid decimal amount: {value!r}")


@router.get("/transactions/sum")
async def sum_transactions(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    account: Optional[str] = Query(default=None),
    source_table: Optional[str] = Query(default=None),
    description_contains: Optional[str] = Query(default=None),
    amount: Optional[str] = Query(default=None),
    amount_min: Optional[str] = Query(default=None),
    amount_max: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    q = (
        select(
            func.coalesce(func.sum(Transaction.amount), 0).label("sum_amount"),
            func.count(Transaction.id).label("row_count"),
        )
        .join(Account, Transaction.account_id == Account.id)
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

    res = await session.execute(q)
    row = res.one()

    return {
        "sum_amount": float(row.sum_amount),
        "row_count": int(row.row_count),
        "start": start.isoformat() if start else None,
        "end": end.isoformat() if end else None,
        "account": account,
        "source_table": source_table,
        "description_contains": description_contains,
    }