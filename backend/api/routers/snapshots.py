from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models import Account, LedgerSnapshot

router = APIRouter(prefix="/api", tags=["snapshots"])


@router.get("/snapshots")
async def list_snapshots(
    account: str | None = Query(default=None, description='Account name, e.g. "checking" or "credit"'),
    session: AsyncSession = Depends(get_session),
):
    q = select(LedgerSnapshot, Account).join(Account)

    if account:
        q = q.where(Account.name == account)

    q = q.order_by(LedgerSnapshot.created_at.desc())

    res = await session.execute(q)
    rows = res.all()

    return [
        {
            "id": snap.id,
            "account": acct.name,
            "ledger_filename": snap.ledger_filename,
            "ledger_sha256": snap.ledger_sha256,
            "tx_min_date": snap.tx_min_date.isoformat(),
            "tx_max_date": snap.tx_max_date.isoformat(),
            "created_at": snap.created_at.isoformat() + "Z",
        }
        for snap, acct in rows
    ]
