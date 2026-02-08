from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models import Account, Transaction

router = APIRouter(prefix="/api", tags=["transactions"])


@router.get("/transactions")
async def list_transactions(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    account: Optional[str] = Query(default=None, description='Account name, e.g. "debit" or "credit"'),
    session: AsyncSession = Depends(get_session),
):
    q = select(Transaction).join(Account)

    if account:
        q = q.where(Account.name == account)
    if start:
        q = q.where(Transaction.date >= start)
    if end:
        q = q.where(Transaction.date <= end)

    q = q.order_by(Transaction.date.asc(), Transaction.id.asc())

    res = await session.execute(q)
    txs = res.scalars().all()

    # Minimal JSON-friendly shape for now (we'll add Pydantic schemas next)
    return [
        {
            "id": tx.id,
            "account_id": tx.account_id,
            "date": tx.date.isoformat(),
            "description": tx.description,
            "amount": float(tx.amount) if isinstance(tx.amount, Decimal) else tx.amount,
            "source_file": tx.source_file,
            "source_row": tx.source_row,
        }
        for tx in txs
    ]

