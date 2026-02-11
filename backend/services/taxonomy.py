from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models import Category, Group, TransactionCategory


class CategoryConflictError(ValueError):
    pass


class ProtectedCategoryError(ValueError):
    pass


class SentinelCategoryMissingError(LookupError):
    pass


UNCLASSIFIED_GROUP_NAME = "Unclassified"
DELETED_CATEGORY_NAME = "Deleted Category"
UNCATEGORIZED_CATEGORY_NAME = "Uncategorized"
PROTECTED_CATEGORY_NAMES = frozenset({DELETED_CATEGORY_NAME, UNCATEGORIZED_CATEGORY_NAME})


def normalize_category_name(name: str) -> str:
    return name.strip()


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


async def is_protected_category_id(session: AsyncSession, category_id: int) -> bool:
    row = (
        await session.execute(
            select(Category.id)
            .join(Group, Group.id == Category.group_id)
            .where(Category.id == category_id)
            .where(Group.name == UNCLASSIFIED_GROUP_NAME)
            .where(Category.name.in_(tuple(PROTECTED_CATEGORY_NAMES)))
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None


async def get_deleted_category_id(session: AsyncSession) -> int:
    deleted_id = (
        await session.execute(
            select(Category.id)
            .join(Group, Group.id == Category.group_id)
            .where(Group.name == UNCLASSIFIED_GROUP_NAME)
            .where(Category.name == DELETED_CATEGORY_NAME)
            .limit(1)
        )
    ).scalar_one_or_none()
    if deleted_id is None:
        raise SentinelCategoryMissingError(
            f'Missing sentinel category: {UNCLASSIFIED_GROUP_NAME} -> "{DELETED_CATEGORY_NAME}"'
        )
    return int(deleted_id)


async def delete_category_reassign_to_deleted(
    session: AsyncSession,
    *,
    category_id: int,
) -> tuple[int, str, int]:
    category_row = (
        await session.execute(
            select(Category.id, Category.name)
            .where(Category.id == category_id)
            .limit(1)
        )
    ).one_or_none()
    if category_row is None:
        raise LookupError(f"Category does not exist: {category_id}")

    if await is_protected_category_id(session, category_id):
        raise ProtectedCategoryError(f"Category is protected and cannot be deleted: {category_id}")

    deleted_category_id = await get_deleted_category_id(session)

    reassigned = await session.execute(
        update(TransactionCategory)
        .where(TransactionCategory.category_id == category_id)
        .values(category_id=deleted_category_id, assigned_at=func.current_timestamp())
    )

    await session.execute(delete(Category).where(Category.id == category_id))
    await session.flush()

    return int(reassigned.rowcount or 0), category_row.name, deleted_category_id


async def rename_category(
    session: AsyncSession,
    *,
    category_id: int,
    new_name: str,
) -> tuple[Category, bool]:
    normalized_name = normalize_category_name(new_name)
    if not normalized_name:
        raise ValueError("Category name cannot be empty")

    category = (
        await session.execute(
            select(Category)
            .where(Category.id == category_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if category is None:
        raise LookupError(f"Category does not exist: {category_id}")

    if await is_protected_category_id(session, category_id):
        raise ProtectedCategoryError(f"Category is protected and cannot be renamed: {category_id}")

    if category.name.lower() == normalized_name.lower():
        return category, False

    existing_conflict = (
        await session.execute(
            select(Category.id)
            .where(func.lower(Category.name) == normalized_name.lower())
            .where(Category.id != category_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing_conflict is not None:
        raise CategoryConflictError(f"Category name already exists: {normalized_name}")

    category.name = normalized_name
    await session.flush()
    return category, True


async def move_category_to_group(
    session: AsyncSession,
    *,
    category_id: int,
    target_group_id: int,
    sort_order: int | None = None,
) -> tuple[Category, bool]:
    category = (
        await session.execute(
            select(Category)
            .where(Category.id == category_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if category is None:
        raise LookupError(f"Category does not exist: {category_id}")

    if await is_protected_category_id(session, category_id):
        raise ProtectedCategoryError(f"Category is protected and cannot be moved: {category_id}")

    target_group = (
        await session.execute(
            select(Group.id)
            .where(Group.id == target_group_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if target_group is None:
        raise LookupError(f"Group does not exist: {target_group_id}")

    changed = category.group_id != target_group_id
    if not changed:
        return category, False

    if sort_order is None:
        max_sort = (
            await session.execute(
                select(func.coalesce(func.max(Category.sort_order), 0))
                .where(Category.group_id == target_group_id)
            )
        ).scalar_one()
        sort_order = int(max_sort) + 1

    category.group_id = target_group_id
    category.sort_order = sort_order
    await session.flush()
    return category, True


def normalize_report_class(report_class: str) -> str:
    normalized = report_class.strip().lower()
    if normalized not in {"auto", "transfer"}:
        raise ValueError("report_class must be one of: auto, transfer")
    return normalized


async def create_category_in_existing_group_id(
    session: AsyncSession,
    *,
    group_id: int,
    category_name: str,
    sort_order: int | None = None,
    report_class: str = "auto",
) -> tuple[Category, bool]:
    cname = normalize_category_name(category_name)
    if not cname:
        raise ValueError("Category name cannot be empty")
    if sort_order is not None and sort_order < 0:
        raise ValueError("sort_order must be >= 0")
    normalized_report_class = normalize_report_class(report_class)

    grp = (await session.execute(select(Group).where(Group.id == group_id).limit(1))).scalar_one_or_none()
    if grp is None:
        raise LookupError(f"Group does not exist: {group_id}")

    existing_same_group = (
        await session.execute(
            select(Category)
            .where(Category.group_id == grp.id)
            .where(func.lower(Category.name) == cname.lower())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing_same_group is not None:
        return existing_same_group, False

    existing_any_group = (
        await session.execute(
            select(Category, Group.name)
            .join(Group, Group.id == Category.group_id)
            .where(func.lower(Category.name) == cname.lower())
            .limit(1)
        )
    ).first()
    if existing_any_group is not None:
        _, other_group_name = existing_any_group
        raise CategoryConflictError(
            f"Category name already exists: {cname} (group: {other_group_name})"
        )

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
        report_class=normalized_report_class,
    )
    session.add(cat)
    await session.flush()
    return cat, True


async def create_category_in_existing_group(
    session: AsyncSession,
    *,
    group_name: str,
    category_name: str,
    sort_order: int | None = None,
    report_class: str = "auto",
) -> tuple[Category, bool]:
    gname = normalize_group_name(group_name)

    grp = (
        await session.execute(select(Group).where(func.lower(Group.name) == gname.lower()).limit(1))
    ).scalar_one_or_none()
    if grp is None:
        raise LookupError(f"Group does not exist: {gname}")

    return await create_category_in_existing_group_id(
        session,
        group_id=grp.id,
        category_name=category_name,
        sort_order=sort_order,
        report_class=report_class,
    )
