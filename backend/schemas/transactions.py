from __future__ import annotations

from pydantic import BaseModel, Field


class TransactionCategoryAssignIn(BaseModel):
    category_id: int = Field(..., ge=1)


class TransactionCategoryAssignmentOut(BaseModel):
    txn_id: int
    category_id: int


class TransactionCategoryMutationOut(BaseModel):
    ok: bool = True
    message: str
    created: bool
    data: TransactionCategoryAssignmentOut
