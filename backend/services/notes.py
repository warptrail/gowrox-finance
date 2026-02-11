from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Transaction, TransactionNote


async def upsert_note(session: AsyncSession, *, txn_id: int, note: str) -> tuple[TransactionNote, bool]:
    # Ensure txn exists
    exists = (
        await session.execute(select(Transaction.id).where(Transaction.id == txn_id).limit(1))
    ).scalar_one_or_none()
    if exists is None:
        raise LookupError(f"Transaction does not exist: {txn_id}")

    row = (
        await session.execute(select(TransactionNote).where(TransactionNote.txn_id == txn_id).limit(1))
    ).scalar_one_or_none()

    if row is None:
        row = TransactionNote(txn_id=txn_id, note=note)
        session.add(row)
        await session.flush()
        return row, True

    row.note = note  # triggers onupdate(updated_at)
    await session.flush()
    return row, False


async def get_note(session: AsyncSession, *, txn_id: int) -> TransactionNote | None:
    return (
        await session.execute(select(TransactionNote).where(TransactionNote.txn_id == txn_id).limit(1))
    ).scalar_one_or_none()


async def delete_note(session: AsyncSession, *, txn_id: int) -> bool:
    row = await get_note(session, txn_id=txn_id)
    if row is None:
        return False
    await session.delete(row)
    return True
