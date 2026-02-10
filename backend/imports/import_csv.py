# backend/imports/import_csv.py
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base, SessionLocal, engine
from imports.schema_bootstrap import apply_schema_bootstrap
from models import Account, LedgerSnapshot, Transaction


REQUIRED_COLUMNS: set[str] = {
    "Date",
    "Description",
    "Inflow",
    "Outflow",
    "SourceTable",
    "SourceFile",
    "SourceRow",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_number(series: pd.Series) -> pd.Series:
    """
    Convert money-ish columns to numeric:
    - handles commas, $ signs, blanks, NaN
    - returns float-ish numeric series
    """
    s = series.fillna(0).astype(str)
    s = s.str.replace(",", "", regex=False).str.replace("$", "", regex=False).str.strip()
    s = s.replace("", "0")
    return pd.to_numeric(s)


def load_ledger_csv(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"{csv_path.name}: missing columns {sorted(missing)}; found: {list(df.columns)}"
        )

    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"]).dt.date
    df["Description"] = df["Description"].fillna("").astype(str)
    df["SourceTable"] = df["SourceTable"].fillna("").astype(str)

    inflow = to_number(df["Inflow"])
    outflow = to_number(df["Outflow"])
    df["AmountSigned"] = inflow - outflow

    # Ensure these are present and usable
    df["SourceFile"] = df["SourceFile"].fillna("").astype(str)
    df["SourceRow"] = pd.to_numeric(df["SourceRow"])

    return df


async def get_or_create_account(session: AsyncSession, name: str, type_: str) -> Account:
    res = await session.execute(select(Account).where(Account.name == name))
    acct = res.scalar_one_or_none()
    if acct:
        return acct

    acct = Account(name=name, type=type_)
    session.add(acct)
    await session.flush()
    return acct


async def snapshot_exists(session: AsyncSession, ledger_sha256: str) -> bool:
    res = await session.execute(
        select(LedgerSnapshot.id)
        .where(LedgerSnapshot.ledger_sha256 == ledger_sha256)
        .limit(1)
    )
    return res.first() is not None


async def autoclassify_uncategorized(session: AsyncSession, ledger_snapshot_id: int) -> int:
    """
    Ensures every transaction in the given snapshot has a category assignment.
    Default: Unclassified → Uncategorized.
    Returns number of rows inserted into transaction_categories.
    """

    uncategorized_id = (
        await session.execute(
            text(
                """
                SELECT c.id
                FROM categories c
                JOIN groups g ON g.id = c.group_id
                WHERE g.name = 'Unclassified' AND c.name = 'Uncategorized'
                LIMIT 1;
                """
            )
        )
    ).scalar_one_or_none()

    if uncategorized_id is None:
        # Defensive: create group/category if missing (shouldn't happen if init_classification ran).
        await session.execute(
            text(
                """
                INSERT INTO groups(name, sort_order)
                SELECT 'Unclassified', 1
                WHERE NOT EXISTS (SELECT 1 FROM groups WHERE name='Unclassified');
                """
            )
        )
        await session.execute(
            text(
                """
                INSERT INTO categories(group_id, name, sort_order, report_class)
                SELECT g.id, 'Uncategorized', 1, 'auto'
                FROM groups g
                WHERE g.name='Unclassified'
                  AND NOT EXISTS (
                    SELECT 1 FROM categories c WHERE c.group_id=g.id AND c.name='Uncategorized'
                  );
                """
            )
        )
        uncategorized_id = (
            await session.execute(
                text(
                    """
                    SELECT c.id
                    FROM categories c
                    JOIN groups g ON g.id = c.group_id
                    WHERE g.name = 'Unclassified' AND c.name = 'Uncategorized'
                    LIMIT 1;
                    """
                )
            )
        ).scalar_one()

    # Fill only missing classifications for txns in this snapshot
    result = await session.execute(
        text(
            """
            INSERT INTO transaction_categories (txn_id, category_id, assigned_at)
            SELECT t.id, :cat_id, CURRENT_TIMESTAMP
            FROM transactions t
            LEFT JOIN transaction_categories tc ON tc.txn_id = t.id
            WHERE t.ledger_snapshot_id = :snap_id
              AND tc.txn_id IS NULL;
            """
        ),
        {"cat_id": uncategorized_id, "snap_id": ledger_snapshot_id},
    )

    return int(result.rowcount or 0)


async def import_ledger(csv_path: Path, account_name: str, account_type: str) -> None:
    df = load_ledger_csv(csv_path)
    file_hash = sha256_file(csv_path)

    tx_min_date = df["Date"].min()
    tx_max_date = df["Date"].max()

    async with SessionLocal() as session:
        acct = await get_or_create_account(session, account_name, account_type)

        if await snapshot_exists(session, file_hash):
            print(f"Skipping {csv_path.name} (already imported: sha256={file_hash[:12]}...)")
            return

        snapshot = LedgerSnapshot(
            account_id=acct.id,
            ledger_filename=csv_path.name,
            ledger_sha256=file_hash,
            tx_min_date=tx_min_date,
            tx_max_date=tx_max_date,
        )
        session.add(snapshot)
        await session.flush()  # snapshot.id available now

        rows: list[Transaction] = []
        for _, r in df.iterrows():
            source_file = r["SourceFile"] if r["SourceFile"] else csv_path.name
            rows.append(
                Transaction(
                    account_id=acct.id,
                    ledger_snapshot_id=snapshot.id,
                    date=r["Date"],
                    description=r["Description"],
                    amount=r["AmountSigned"],
                    source_table=r["SourceTable"],
                    source_file=source_file,
                    source_row=int(r["SourceRow"]),
                )
            )

        session.add_all(rows)

        # Ensure transaction rows are in DB (t.id exists) before INSERT..SELECT into transaction_categories
        await session.flush()

        inserted = await autoclassify_uncategorized(session, snapshot.id)
        print(f"Auto-classified {inserted} txns as Uncategorized for snapshot_id={snapshot.id}")

        await session.commit()

    print(
        f"Imported {len(df)} rows from {csv_path.name} "
        f"({tx_min_date} → {tx_max_date}) sha256={file_hash[:12]}..."
    )


async def main() -> None:
    # Create tables + apply triggers/indexes
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_schema_bootstrap(engine)

    backend_dir = Path(__file__).resolve().parents[1]  # .../backend
    project_root = backend_dir.parent                  # .../gowrox-finance
    csv_dir = project_root / "csv"

    credit_csv = csv_dir / "ledger_credit_20241227_20260126.csv"
    checking_csv = csv_dir / "ledger_checking_20241226_20260127.csv"

    if not credit_csv.exists():
        raise FileNotFoundError(f"Missing: {credit_csv}")
    if not checking_csv.exists():
        raise FileNotFoundError(f"Missing: {checking_csv}")

    await import_ledger(credit_csv, account_name="credit", account_type="credit")
    await import_ledger(checking_csv, account_name="checking", account_type="debit")


if __name__ == "__main__":
    asyncio.run(main())