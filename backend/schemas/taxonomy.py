from __future__ import annotations

from pydantic import BaseModel, Field


class CategoryCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    sort_order: int | None = None
    report_class: str = "auto"


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