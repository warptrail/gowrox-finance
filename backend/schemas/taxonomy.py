from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CategoryCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    sort_order: int | None = None
    report_class: Literal["auto", "transfer"] = "auto"


class CategoryRenameIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)


class CategoryMoveIn(BaseModel):
    group_id: int = Field(..., ge=1)
    sort_order: int | None = Field(default=None, ge=0)


class CategoryOut(BaseModel):
    id: int
    group_id: int
    name: str
    sort_order: int
    report_class: str

class CategoryBriefOut(BaseModel):
    id: int
    name: str
    sort_order: int
    report_class: str

class GroupWithCategoriesOut(BaseModel):
    id: int
    name: str
    sort_order: int
    categories: list[CategoryBriefOut]


class TaxonomyCategoryOut(BaseModel):
    category_id: int
    category_name: str


class TaxonomyGroupOut(BaseModel):
    group_id: int
    group_name: str
    category_count: int
    categories: list[TaxonomyCategoryOut]


class CategoryMutationOut(BaseModel):
    ok: bool = True
    message: str
    created: bool
    data: CategoryOut


class CategoryDeleteResultOut(BaseModel):
    category_id: int
    category_name: str
    reassigned_transactions: int
    reassigned_to_category_id: int


class CategoryDeleteMutationOut(BaseModel):
    ok: bool = True
    message: str
    data: CategoryDeleteResultOut
