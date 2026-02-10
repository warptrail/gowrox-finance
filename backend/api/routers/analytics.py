# backend/api/routers/analytics.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from schemas.reports import UncategorizedCountOut
from services.reports import uncategorized_count

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/uncategorized-count", response_model=UncategorizedCountOut)
async def get_uncategorized_count(
    year: int = 2025,
    session: AsyncSession = Depends(get_session),
) -> UncategorizedCountOut:
    count = await uncategorized_count(session, year=year)
    return UncategorizedCountOut(year=year, count=count)