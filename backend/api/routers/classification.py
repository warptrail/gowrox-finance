from collections import OrderedDict
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from models import Transaction, TransactionCategory, Category, Group

router = APIRouter(prefix="/api", tags=["classification"])


@router.get("/categories")
async def get_categories(session: AsyncSession = Depends(get_session)):
    # Pull groups + categories in one query
    q = (
        select(Group, Category)
        .outerjoin(Category, Category.group_id == Group.id)
        .order_by(Group.sort_order.asc(), Group.name.asc(), Category.sort_order.asc(), Category.name.asc())
    )

    res = await session.execute(q)
    rows = res.all()

    # Group rows into a stable JSON shape
    grouped: "OrderedDict[int, dict]" = OrderedDict()

    for grp, cat in rows:
        if grp.id not in grouped:
            grouped[grp.id] = {
                "group_id": grp.id,
                "group_name": grp.name,
                "sort_order": grp.sort_order,
                "categories": [],
            }

        if cat is not None:
            grouped[grp.id]["categories"].append(
                {
                    "category_id": cat.id,
                    "name": cat.name,
                    "report_class": cat.report_class,
                    "sort_order": cat.sort_order,
                    "group_id": cat.group_id,
                }
            )

    return list(grouped.values())
    
class SetTransactionCategoryRequest(BaseModel):
    category_id: int


@router.put("/transactions/{txn_id}/category")
async def set_transaction_category(
    txn_id: int,
    payload: SetTransactionCategoryRequest,
    session: AsyncSession = Depends(get_session),
):
    # 1) Ensure txn exists (immutable fact)
    txn = await session.get(Transaction, txn_id)
    if txn is None:
        raise HTTPException(status_code=404, detail=f"Transaction not found: {txn_id}")

    # 2) Ensure category exists (taxonomy)
    cat = await session.get(Category, payload.category_id)
    if cat is None:
        raise HTTPException(status_code=404, detail=f"Category not found: {payload.category_id}")

    # 3) Ensure assignment row exists (it should, due to backfill)
    link = await session.get(TransactionCategory, txn_id)
    if link is None:
        # Fallback safety: create it if DB is partial (idempotent resilience)
        link = TransactionCategory(txn_id=txn_id, category_id=cat.id, assigned_at=datetime.utcnow())
        session.add(link)
    else:
        link.category_id = cat.id
        link.assigned_at = datetime.utcnow()

    await session.commit()

    # 4) Return enriched info (group/name/report_class)
    # Fetch group name with a small join
    q = (
        select(Category, Group)
        .join(Group, Group.id == Category.group_id)
        .where(Category.id == cat.id)
    )
    res = await session.execute(q)
    cat2, grp = res.one()

    return {
        "txn_id": txn_id,
        "category_id": cat2.id,
        "category_name": cat2.name,
        "category_report_class": cat2.report_class,
        "group_id": grp.id,
        "group_name": grp.name,
        "assigned_at": link.assigned_at.isoformat() + "Z",
    }