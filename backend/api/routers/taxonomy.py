from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from schemas.taxonomy import GroupWithCategoriesOut, CategoryBriefOut, CategoryCreateIn, CategoryOut
from services.taxonomy import taxonomy_map, create_category_in_existing_group

router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])

@router.get("/map", response_model=list[GroupWithCategoriesOut])
async def get_taxonomy_map(session: AsyncSession = Depends(get_session)):
    rows = await taxonomy_map(session)
    return [
        GroupWithCategoriesOut(
            id=g.id,
            name=g.name,
            sort_order=g.sort_order,
            categories=[
                CategoryBriefOut(
                    id=c.id,
                    name=c.name,
                    sort_order=c.sort_order,
                    report_class=c.report_class,
                )
                for c in cats
            ],
        )
        for g, cats in rows
    ]

@router.post("/groups/{group_name}/categories", response_model=CategoryOut)
async def add_category(
    group_name: str,
    payload: CategoryCreateIn,
    session: AsyncSession = Depends(get_session),
) -> CategoryOut:
    try:
        cat = await create_category_in_existing_group(
            session,
            group_name=group_name,
            category_name=payload.name,
            sort_order=payload.sort_order,
            report_class=payload.report_class,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        # conflict (duplicate category name across groups)
        raise HTTPException(status_code=409, detail=str(e))

    await session.commit()

    return CategoryOut(
        id=cat.id,
        group_id=cat.group_id,
        name=cat.name,
        sort_order=cat.sort_order,
        report_class=cat.report_class,
    )
