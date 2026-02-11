from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from schemas.transactions import (
    TransactionCategoryAssignIn,
    TransactionCategoryAssignmentOut,
    TransactionCategoryMutationOut,
)
from services.transactions import (
    AmbiguousTaxonomyFilterError,
    CategoryAssignmentConflictError,
    CategoryAssignmentPersistenceError,
    InvalidAmountError,
    InvalidSortError,
    TransactionListFilters,
    assign_transaction_category as assign_transaction_category_service,
    list_transactions as list_transactions_service,
)

router = APIRouter(prefix="/api", tags=["transactions"])

@router.get("/transactions")
async def list_transactions(
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    account: Optional[str] = Query(default=None),
    source_table: Optional[str] = Query(default=None),
    description_contains: Optional[str] = Query(default=None),
    amount: Optional[str] = Query(default=None, description="Exact amount match, e.g. -19.99 or 19.99"),
    amount_min: Optional[str] = Query(default=None, description="Minimum amount (inclusive)"),
    amount_max: Optional[str] = Query(default=None, description="Maximum amount (inclusive)"),
    group_id: Optional[int] = Query(default=None),
    group_name: Optional[str] = Query(default=None),
    category_id: Optional[int] = Query(default=None),
    category_name: Optional[str] = Query(default=None),
    sort_by: str = Query(default="date"),
    sort_dir: str = Query(default="asc"),
    limit: int = Query(default=200, ge=1, le=5000),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    try:
        return await list_transactions_service(
            session,
            filters=TransactionListFilters(
                start=start,
                end=end,
                account=account,
                source_table=source_table,
                description_contains=description_contains,
                amount=amount,
                amount_min=amount_min,
                amount_max=amount_max,
                group_id=group_id,
                group_name=group_name,
                category_id=category_id,
                category_name=category_name,
                sort_by=sort_by,
                sort_dir=sort_dir,
                limit=limit,
                offset=offset,
            ),
        )
    except InvalidAmountError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except InvalidSortError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except AmbiguousTaxonomyFilterError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.patch("/transactions/{txn_id}/category", response_model=TransactionCategoryMutationOut)
async def assign_transaction_category(
    txn_id: int,
    payload: TransactionCategoryAssignIn,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> TransactionCategoryMutationOut:
    try:
        created, message = await assign_transaction_category_service(
            session,
            txn_id=txn_id,
            category_id=payload.category_id,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except CategoryAssignmentConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except CategoryAssignmentPersistenceError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    response.status_code = 201 if created else 200

    return TransactionCategoryMutationOut(
        message=message,
        created=created,
        data=TransactionCategoryAssignmentOut(txn_id=txn_id, category_id=payload.category_id),
    )
