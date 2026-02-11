from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from schemas.taxonomy import (
    CategoryBriefOut,
    CategoryCreateIn,
    CategoryDeleteMutationOut,
    CategoryDeleteResultOut,
    CategoryMoveIn,
    CategoryMutationOut,
    CategoryOut,
    CategoryRenameIn,
    GroupWithCategoriesOut,
    TaxonomyCategoryOut,
    TaxonomyGroupOut,
)
from services.taxonomy import (
    CategoryConflictError,
    ProtectedCategoryError,
    SentinelCategoryMissingError,
    create_category_in_existing_group,
    create_category_in_existing_group_id,
    delete_category_reassign_to_deleted,
    move_category_to_group,
    rename_category,
    taxonomy_map,
)

router = APIRouter(tags=["taxonomy"])
legacy_router = APIRouter(prefix="/taxonomy", tags=["taxonomy"])
api_router = APIRouter(prefix="/api/taxonomy", tags=["taxonomy"])


@legacy_router.get("/map", response_model=list[GroupWithCategoriesOut])
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


@api_router.get("/groups", response_model=list[TaxonomyGroupOut])
async def list_taxonomy_groups(session: AsyncSession = Depends(get_session)) -> list[TaxonomyGroupOut]:
    try:
        rows = await taxonomy_map(session)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load taxonomy groups: {exc}") from exc

    return [
        TaxonomyGroupOut(
            group_id=g.id,
            group_name=g.name,
            category_count=len(cats),
            categories=[
                TaxonomyCategoryOut(
                    category_id=c.id,
                    category_name=c.name,
                )
                for c in cats
            ],
        )
        for g, cats in rows
    ]


@api_router.get("", response_model=list[TaxonomyGroupOut])
async def list_taxonomy(session: AsyncSession = Depends(get_session)) -> list[TaxonomyGroupOut]:
    return await list_taxonomy_groups(session)


@api_router.post("/groups/{group_id}/categories", response_model=CategoryMutationOut)
async def add_category_by_group_id(
    group_id: int,
    payload: CategoryCreateIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> CategoryMutationOut:
    try:
        cat, created = await create_category_in_existing_group_id(
            session,
            group_id=group_id,
            category_name=payload.name,
            sort_order=payload.sort_order,
            report_class=payload.report_class,
        )
        await session.commit()
    except LookupError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except CategoryConflictError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Category create conflict: {e}") from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create category: {e}") from e

    if created:
        response.status_code = 201
        message = "Category created"
    else:
        response.status_code = 200
        message = "Category already exists in group"

    return CategoryMutationOut(
        message=message,
        created=created,
        data=CategoryOut(
            id=cat.id,
            group_id=cat.group_id,
            name=cat.name,
            sort_order=cat.sort_order,
            report_class=cat.report_class,
        ),
    )


@legacy_router.post("/groups/{group_name}/categories", response_model=CategoryMutationOut)
async def add_category(
    group_name: str,
    payload: CategoryCreateIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> CategoryMutationOut:
    try:
        cat, created = await create_category_in_existing_group(
            session,
            group_name=group_name,
            category_name=payload.name,
            sort_order=payload.sort_order,
            report_class=payload.report_class,
        )
        await session.commit()
    except LookupError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except CategoryConflictError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Category create conflict: {e}") from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create category: {e}") from e

    if created:
        response.status_code = 201
        message = "Category created"
    else:
        response.status_code = 200
        message = "Category already exists in group"

    return CategoryMutationOut(
        message=message,
        created=created,
        data=CategoryOut(
            id=cat.id,
            group_id=cat.group_id,
            name=cat.name,
            sort_order=cat.sort_order,
            report_class=cat.report_class,
        ),
    )


@api_router.delete("/categories/{category_id}", response_model=CategoryDeleteMutationOut)
async def delete_category(
    category_id: int,
    session: AsyncSession = Depends(get_session),
) -> CategoryDeleteMutationOut:
    try:
        reassigned_count, deleted_name, deleted_category_id = await delete_category_reassign_to_deleted(
            session,
            category_id=category_id,
        )
        await session.commit()
    except SentinelCategoryMissingError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    except LookupError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except ProtectedCategoryError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Category delete conflict: {e}") from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete category: {e}") from e

    return CategoryDeleteMutationOut(
        message="Category deleted and transactions reassigned",
        data=CategoryDeleteResultOut(
            category_id=category_id,
            category_name=deleted_name,
            reassigned_transactions=reassigned_count,
            reassigned_to_category_id=deleted_category_id,
        ),
    )


@api_router.patch("/categories/{category_id}", response_model=CategoryMutationOut)
async def rename_category_endpoint(
    category_id: int,
    payload: CategoryRenameIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> CategoryMutationOut:
    try:
        category, changed = await rename_category(
            session,
            category_id=category_id,
            new_name=payload.name,
        )
        await session.commit()
    except LookupError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except ProtectedCategoryError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except CategoryConflictError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Category rename conflict: {e}") from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to rename category: {e}") from e

    response.status_code = 200
    return CategoryMutationOut(
        message="Category renamed" if changed else "Category name unchanged",
        created=False,
        data=CategoryOut(
            id=category.id,
            group_id=category.group_id,
            name=category.name,
            sort_order=category.sort_order,
            report_class=category.report_class,
        ),
    )


@api_router.patch("/categories/{category_id}/group", response_model=CategoryMutationOut)
async def move_category_endpoint(
    category_id: int,
    payload: CategoryMoveIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> CategoryMutationOut:
    try:
        category, changed = await move_category_to_group(
            session,
            category_id=category_id,
            target_group_id=payload.group_id,
            sort_order=payload.sort_order,
        )
        await session.commit()
    except LookupError as e:
        await session.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    except ProtectedCategoryError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except CategoryConflictError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        await session.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail=f"Category move conflict: {e}") from e
    except SQLAlchemyError as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to move category: {e}") from e

    response.status_code = 200
    return CategoryMutationOut(
        message="Category moved to new group" if changed else "Category already in target group",
        created=False,
        data=CategoryOut(
            id=category.id,
            group_id=category.group_id,
            name=category.name,
            sort_order=category.sort_order,
            report_class=category.report_class,
        ),
    )


router.include_router(legacy_router)
router.include_router(api_router)
