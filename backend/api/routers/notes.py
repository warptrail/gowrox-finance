from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from schemas.notes import NoteMutationOut, NoteOut, NoteUpsertIn
from services.notes import delete_note, get_note, upsert_note

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("/transactions/{txn_id}", response_model=NoteOut)
async def read_note(txn_id: int, session: AsyncSession = Depends(get_session)) -> NoteOut:
    row = await get_note(session, txn_id=txn_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteOut(txn_id=row.txn_id, note=row.note, updated_at=row.updated_at)


@router.put("/transactions/{txn_id}", response_model=NoteMutationOut)
async def write_note(
    txn_id: int, payload: NoteUpsertIn, response: Response, session: AsyncSession = Depends(get_session)
) -> NoteMutationOut:
    try:
        row, created = await upsert_note(session, txn_id=txn_id, note=payload.note)
        await session.commit()
    except LookupError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upsert note: {e}") from e

    if created:
        response.status_code = 201
        message = "Note created"
    else:
        response.status_code = 200
        message = "Note updated"

    return NoteMutationOut(
        message=message,
        created=created,
        data=NoteOut(txn_id=row.txn_id, note=row.note, updated_at=row.updated_at),
    )


@router.delete("/transactions/{txn_id}")
async def remove_note(txn_id: int, session: AsyncSession = Depends(get_session)):
    ok = await delete_note(session, txn_id=txn_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    await session.commit()
    return {"ok": True}
