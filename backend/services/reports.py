# backend/services/reports.py
from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models import Transaction, TransactionCategory, Category, Group


async def uncategorized_count(session: AsyncSession, year: int) -> int:
    start = f"{year:04d}-01-01"
    end = f"{year + 1:04d}-01-01"

    q = (
        select(func.count())
        .select_from(Transaction)
        .join(TransactionCategory, TransactionCategory.txn_id == Transaction.id)
        .join(Category, Category.id == TransactionCategory.category_id)
        .join(Group, Group.id == Category.group_id)
        .where(Group.name == "Unclassified")
        .where(Category.name == "Uncategorized")
        .where(Transaction.date >= start)
        .where(Transaction.date < end)
    )

    return int((await session.execute(q)).scalar_one())