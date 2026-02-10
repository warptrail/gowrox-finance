from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel


class TaxonomyCountOut(BaseModel):
    group: str
    category: Optional[str]
    tags: Optional[List[str]]  # reserved for future use (no DB yet)
    start: date
    end: date
    count: int
