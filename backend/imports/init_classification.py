# init_classification.py
from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import SessionLocal, engine, Base
from models import Group, Category
from imports.schema_bootstrap import apply_schema_bootstrap



TAXONOMY: list[dict[str, object]] = [
    {"group": "Unclassified", "categories": ["Uncategorized", "Deleted Category"]},

    {"group": "Income", "categories": [
        "Wages",
        "Freelance income",
    ]},

    {"group": "Housing", "categories": [
        "Rent",
        "Mortgage interest",
    ]},

    {"group": "Utilities", "categories": [
        "Electricity",
        "Natural gas",
        "Water",
        "Trash service",
    ]},

    {"group": "Equipment", "categories": [
        "Appliance",
        "Computer hardware",
        "Software license",
    ]},

    {"group": "Household", "categories": [
        "Cleaning supplies",
        "Paper goods",
    ]},

    {"group": "Personal & Lifestyle", "categories": [
        "Clothing",
        "Haircut",
    ]},

    {"group": "Entertainment", "categories": [
        "Streaming subscription",
        "Live event ticket",
    ]},

    {"group": "Education", "categories": [
        "Online course",
        "Books",
    ]},

    {"group": "Food", "categories": [
        "Groceries",
        "Restaurant",
        "Coffee",
    ]},

    {"group": "Health", "categories": [
        "Doctor visit",
        "Prescription medication",
    ]},

    {"group": "Transportation", "categories": [
        "Fuel",
        "Public transit",
        "Vehicle maintenance",
    ]},

    {"group": "Debt", "categories": [
        "Credit card interest",
        "Loan principal payment",
    ]},

    {"group": "Transfers & Savings", "categories": [
        "Account transfer",
        "Credit Card Payment",
    ]},

    {"group": "Investments", "categories": [
        "Brokerage contribution",
    ]},

    {"group": "Taxation", "categories": [
        "Income tax payment",
    ]},

    {"group": "Legal & Penalties", "categories": [
        "Fine",
        "Legal fee",
    ]},
]

async def ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_schema_bootstrap(engine)


async def get_or_create_group(session: AsyncSession, name: str, sort_order: int) -> tuple[Group, bool]:
    res = await session.execute(select(Group).where(Group.name == name))
    grp = res.scalar_one_or_none()
    if grp:
        # Only gently set order if still default
        if grp.sort_order == 0 and sort_order != 0:
            grp.sort_order = sort_order
        return grp, False

    grp = Group(name=name, sort_order=sort_order)
    session.add(grp)
    await session.flush()  # assigns grp.id
    return grp, True


async def get_or_create_category(
    session: AsyncSession,
    *,
    group_id: int,
    name: str,
    sort_order: int,
    report_class: str,
) -> tuple[Category, bool]:
    # Matches uq_categories_group_name (group_id, name)
    res = await session.execute(
        select(Category).where(
            Category.group_id == group_id,
            Category.name == name,
        )
    )
    cat = res.scalar_one_or_none()
    if cat:
        # Gentle nudges; avoid clobbering curated edits
        if cat.sort_order == 0 and sort_order != 0:
            cat.sort_order = sort_order
        if cat.report_class == "auto" and report_class != "auto":
            cat.report_class = report_class
        return cat, False

    cat = Category(
        group_id=group_id,
        name=name,
        sort_order=sort_order,
        report_class=report_class,
    )
    session.add(cat)
    return cat, True


async def init_classification() -> None:
    await ensure_schema()

    created_groups = 0
    created_categories = 0

    async with SessionLocal() as session:
        for g_idx, entry in enumerate(TAXONOMY, start=1):
            group_name = str(entry["group"])
            category_names = [str(x) for x in entry["categories"]]  # type: ignore[index]

            group, g_created = await get_or_create_group(session, group_name, sort_order=g_idx)
            if g_created:
                created_groups += 1

            report_class = "transfer" if group_name == "Transfers & Savings" else "auto"

            for c_idx, cat_name in enumerate(category_names, start=1):
                _, c_created = await get_or_create_category(
                    session,
                    group_id=group.id,
                    name=cat_name,
                    sort_order=c_idx,
                    report_class=report_class,
                )
                if c_created:
                    created_categories += 1

        await session.commit()

    print(
        "init_classification: "
        f"created_groups={created_groups}, created_categories={created_categories} "
        "(idempotent)"
    )


if __name__ == "__main__":
    asyncio.run(init_classification())
