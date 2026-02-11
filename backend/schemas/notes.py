from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class NoteUpsertIn(BaseModel):
    note: str


class NoteOut(BaseModel):
    txn_id: int
    note: str
    updated_at: datetime


class NoteMutationOut(BaseModel):
    ok: bool = True
    message: str
    created: bool
    data: NoteOut
