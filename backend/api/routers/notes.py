from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from schemas.notes import NoteOut, NoteUpsertIn
from services.notes import delete_note, get_note, upsert_note

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/transactions/{txn_id}", response_model=NoteOut)
async def read_note(txn_id: int, session: AsyncSession = Depends(get_session)) -> NoteOut:
    row = await get_note(session, txn_id=txn_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteOut(txn_id=row.txn_id, note=row.note, updated_at=row.updated_at)


@router.put("/transactions/{txn_id}", response_model=NoteOut)
async def write_note(
    txn_id: int, payload: NoteUpsertIn, session: AsyncSession = Depends(get_session)
) -> NoteOut:
    try:
        row = await upsert_note(session, txn_id=txn_id, note=payload.note)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await session.commit()
    return NoteOut(txn_id=row.txn_id, note=row.note, updated_at=row.updated_at)


@router.delete("/transactions/{txn_id}")
async def remove_note(txn_id: int, session: AsyncSession = Depends(get_session)):
    ok = await delete_note(session, txn_id=txn_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    await session.commit()
    return {"ok": True}