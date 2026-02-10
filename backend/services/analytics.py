from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Category, Group, Transaction, TransactionCategory


def _first_day_of_month(d: date) -> date:
    return d.replace(day=1)


def _first_day_next_month(d: date) -> date:
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def resolve_period(*, start: date | None, end: date | None, period: str | None) -> tuple[date, date]:
    """
    Returns (start_inclusive, end_exclusive) using half-open interval [start, end).

    Precedence:
      1) If period is provided, it wins.
      2) Else start/end must both be provided.
    """
    today = date.today()

    if period:
        p = period.strip().lower()

        if p == "this_month":
            s = _first_day_of_month(today)
            e = _first_day_next_month(today)
            return s, e

        if p == "last_month":
            this_month = _first_day_of_month(today)
            last_month_end = this_month
            last_month_start = _first_day_of_month(last_month_end - timedelta(days=1))
            return last_month_start, last_month_end

        if p == "ytd":
            return date(today.year, 1, 1), date(today.year + 1, 1, 1)

        if p.startswith("year_"):
            year = int(p.split("_", 1)[1])
            return date(year, 1, 1), date(year + 1, 1, 1)

        raise ValueError(f"Unknown period preset: {period!r}")

    if start is None or end is None:
        raise ValueError("Provide either period=... or both start=YYYY-MM-DD and end=YYYY-MM-DD")

    if end <= start:
        raise ValueError("end must be after start")

    return start, end


async def taxonomy_count(
    session: AsyncSession,
    *,
    group: str,
    category: str,
    start: date,
    end: date,
    tags: Sequence[str] | None = None,  # reserved for future use
) -> int:
    """
    Count txns within [start, end) assigned to (group, category).

    `tags` is accepted for forward compatibility but ignored until tags exist in DB.
    """
    _ = tags  # intentionally unused for now

    q = (
        select(func.count())
        .select_from(Transaction)
        .join(TransactionCategory, TransactionCategory.txn_id == Transaction.id)
        .join(Category, Category.id == TransactionCategory.category_id)
        .join(Group, Group.id == Category.group_id)
        .where(Group.name == group)
        .where(Category.name == category)
        .where(Transaction.date >= start)
        .where(Transaction.date < end)
    )
    return int((await session.execute(q)).scalar_one())
