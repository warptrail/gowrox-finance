from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from schemas.analytics import TaxonomyCountOut
from services.analytics import resolve_period, taxonomy_count

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/taxonomy-count", response_model=TaxonomyCountOut)
async def get_taxonomy_count(
    group: str = Query(..., description="Group name, e.g. 'Unclassified'"),
    category: str = Query(..., description="Category name, e.g. 'Uncategorized'"),
    start: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    end: date | None = Query(None, description="Exclusive end date (YYYY-MM-DD)"),
    period: str | None = Query(None, description="Preset: this_month, last_month, ytd, year_2025, ..."),
    tags: Optional[List[str]] = Query(None, description="Reserved for future use; ignored for now"),
    session: AsyncSession = Depends(get_session),
) -> TaxonomyCountOut:
    try:
        start_d, end_d = resolve_period(start=start, end=end, period=period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    count = await taxonomy_count(
        session,
        group=group,
        category=category,
        start=start_d,
        end=end_d,
        tags=tags,
    )

    return TaxonomyCountOut(
        group=group,
        category=category,
        tags=tags,
        start=start_d,
        end=end_d,
        count=count,
    )
