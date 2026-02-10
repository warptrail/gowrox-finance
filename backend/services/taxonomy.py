from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Category, Group


def normalize_category_name(name: str) -> str:
    # case-insensitive global uniqueness
    return name.strip().lower()


def normalize_group_name(name: str) -> str:
    return name.strip()
    

async def taxonomy_map(session: AsyncSession) -> list[tuple[Group, list[Category]]]:
    # Fetch all groups ordered
    groups = (
        await session.execute(select(Group).order_by(Group.sort_order.asc(), Group.name.asc()))
    ).scalars().all()

    # Fetch all categories ordered
    cats = (
        await session.execute(
            select(Category).order_by(Category.group_id.asc(), Category.sort_order.asc(), Category.name.asc())
        )
    ).scalars().all()

    # Group categories by group_id
    by_gid: dict[int, list[Category]] = {}
    for c in cats:
        by_gid.setdefault(c.group_id, []).append(c)

    return [(g, by_gid.get(g.id, [])) for g in groups]


async def create_category_in_existing_group(
    session: AsyncSession,
    *,
    group_name: str,
    category_name: str,
    sort_order: int | None = None,
    report_class: str = "auto",
) -> Category:
    gname = normalize_group_name(group_name)
    cname = normalize_category_name(category_name)

    if not cname:
        raise ValueError("Category name cannot be empty")

    # Group must exist
    grp = (
        await session.execute(select(Group).where(Group.name == gname).limit(1))
    ).scalar_one_or_none()
    if grp is None:
        raise LookupError(f"Group does not exist: {gname}")

    # Global uniqueness: does this category exist anywhere?
    existing = (
        await session.execute(select(Category).where(Category.name == cname).limit(1))
    ).scalar_one_or_none()

    if existing is not None:
        # If it exists under the same group, return it (idempotent)
        if existing.group_id == grp.id:
            return existing
        # Otherwise conflict
        other_group = (
            await session.execute(select(Group.name).where(Group.id == existing.group_id).limit(1))
        ).scalar_one_or_none()
        raise ValueError(f"Category name already exists: {cname} (group: {other_group})")

    # Auto sort_order if not provided
    if sort_order is None:
        max_sort = (
            await session.execute(
                select(func.coalesce(func.max(Category.sort_order), 0))
                .where(Category.group_id == grp.id)
            )
        ).scalar_one()
        sort_order = int(max_sort) + 1

    cat = Category(
        group_id=grp.id,
        name=cname,
        sort_order=sort_order,
        report_class=report_class,
    )
    session.add(cat)
    await session.flush()
    return cat
