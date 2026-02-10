# backend/imports/schema_bootstrap.py
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

SQL_STATEMENTS: list[str] = [
    # --- Make imported transaction fields immutable -------------------------
    """
    CREATE TRIGGER IF NOT EXISTS trg_transactions_immutable_imported
    BEFORE UPDATE ON transactions
    FOR EACH ROW
    WHEN
      NEW.account_id         != OLD.account_id OR
      NEW.ledger_snapshot_id != OLD.ledger_snapshot_id OR
      NEW.date               != OLD.date OR
      NEW.description        != OLD.description OR
      NEW.amount             != OLD.amount OR
      NEW.source_table       != OLD.source_table OR
      NEW.source_file        != OLD.source_file OR
      NEW.source_row         != OLD.source_row
    BEGIN
      SELECT RAISE(ABORT, 'transactions are immutable: imported fields cannot be updated');
    END;
    """,

    # --- Optional: make transactions append-only (no deletes) ----------------
    """
    CREATE TRIGGER IF NOT EXISTS trg_transactions_no_delete
    BEFORE DELETE ON transactions
    FOR EACH ROW
    BEGIN
      SELECT RAISE(ABORT, 'transactions are append-only: deletes are not allowed');
    END;
    """,

    # --- Helpful indexes ----------------------------------------------------
    # You already have:
    #   - index=True on account_id, ledger_snapshot_id, date
    #   - explicit composite Index("ix_transactions_account_date", account_id, date)
    # So this one is optional; keep it if you query snapshot->transactions often.
    "CREATE INDEX IF NOT EXISTS ix_transactions_ledger_snapshot_id ON transactions(ledger_snapshot_id);",

    # This MUST be txn_id (PK) in your schema, not transaction_id.
    "CREATE INDEX IF NOT EXISTS ix_transaction_categories_txn_id ON transaction_categories(txn_id);",
    "CREATE INDEX IF NOT EXISTS ix_transaction_categories_category_id ON transaction_categories(category_id);",
]

async def apply_schema_bootstrap(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for stmt in SQL_STATEMENTS:
            await conn.exec_driver_sql(stmt)