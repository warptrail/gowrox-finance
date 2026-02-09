from __future__ import annotations

import asyncio

from sqlalchemy import select, text

from db import SessionLocal, engine, Base
from models import Group, Category, TransactionCategory  # and Transaction exists in models.py


async def ensure_group(session, name: str, sort_order: int = 0) -> int:
    # Idempotent insert for SQLite
    await session.execute(
        text(
            """
            INSERT OR IGNORE INTO groups (name, sort_order)
            VALUES (:name, :sort_order)
            """
        ),
        {"name": name, "sort_order": sort_order},
    )
    group_id = await session.scalar(select(Group.id).where(Group.name == name))
    if group_id is None:
        raise RuntimeError(f"Failed to ensure group: {name}")
    return int(group_id)


async def ensure_category(
    session,
    group_id: int,
    name: str,
    report_class: str = "auto",
    sort_order: int = 0,
) -> int:
    await session.execute(
        text(
            """
            INSERT OR IGNORE INTO categories (group_id, name, report_class, sort_order)
            VALUES (:group_id, :name, :report_class, :sort_order)
            """
        ),
        {
            "group_id": group_id,
            "name": name,
            "report_class": report_class,
            "sort_order": sort_order,
        },
    )
    cat_id = await session.scalar(
        select(Category.id).where(Category.group_id == group_id, Category.name == name)
    )
    if cat_id is None:
        raise RuntimeError(f"Failed to ensure category: {name}")
    return int(cat_id)


async def seed_and_backfill() -> None:
    # 1) Ensure tables exist (includes your new classification tables)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        # 2) Seed Groups + Categories
        unclassified_id = await ensure_group(session, "Unclassified", sort_order=0)
        transfers_id = await ensure_group(session, "Transfers", sort_order=1)

        uncategorized_id = await ensure_category(
            session,
            group_id=unclassified_id,
            name="Uncategorized",
            report_class="auto",
            sort_order=0,
        )
        
        await ensure_category(
            session,
            group_id=unclassified_id,
            name="Forgotten",
            report_class="auto",
            sort_order=1,
        )
        await ensure_category(
            session,
            group_id=transfers_id,
            name="Credit Card Payment",
            report_class="transfer",
            sort_order=0,
        )
        await ensure_category(
            session,
            group_id=transfers_id,
            name="Balance Transfer",
            report_class="transfer",
            sort_order=1,
        )
        await ensure_category(
            session,
            group_id=transfers_id,
            name="Internal Transfer",
            report_class="transfer",
            sort_order=2,
        )

        await session.commit()

        # 3) Backfill: assign EVERY txn -> Uncategorized (idempotent)
        #
        # Uses OR IGNORE so re-running won't overwrite anything or error.
        # txn_id is the PK in transaction_categories, so duplicates are impossible.
        await session.execute(
            text(
                """
                INSERT OR IGNORE INTO transaction_categories (txn_id, category_id, assigned_at)
                SELECT t.id, :uncat_id, CURRENT_TIMESTAMP
                FROM transactions t
                """
            ),
            {"uncat_id": uncategorized_id},
        )
        await session.commit()

        # Optional: quick sanity count (how many assignments exist)
        assigned = await session.scalar(text("SELECT COUNT(*) FROM transaction_categories"))
        print(f"[init_classification] Seeded taxonomy. Backfilled assignments: {assigned}")


def main() -> None:
    asyncio.run(seed_and_backfill())


if __name__ == "__main__":
    main()
