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

    # --- Protected taxonomy categories cannot be deleted --------------------
    """
    CREATE TRIGGER IF NOT EXISTS trg_categories_protect_sentinel_delete
    BEFORE DELETE ON categories
    FOR EACH ROW
    WHEN EXISTS (
      SELECT 1
      FROM groups g
      WHERE g.id = OLD.group_id
        AND g.name = 'Unclassified'
        AND OLD.name IN ('Deleted Category', 'Uncategorized')
    )
    BEGIN
      SELECT RAISE(ABORT, 'protected category cannot be deleted');
    END;
    """,

    """
    CREATE TRIGGER IF NOT EXISTS trg_categories_protect_sentinel_update
    BEFORE UPDATE ON categories
    FOR EACH ROW
    WHEN OLD.group_id = 1
      AND OLD.name IN ('Deleted Category', 'Uncategorized')
    BEGIN
      SELECT RAISE(ABORT, 'protected category cannot be updated');
    END;
    """,

    # --- Ensure every transaction has a category assignment -----------------
    """
    CREATE TRIGGER IF NOT EXISTS trg_transactions_default_uncategorized
    AFTER INSERT ON transactions
    FOR EACH ROW
    WHEN NOT EXISTS (SELECT 1 FROM transaction_categories tc WHERE tc.txn_id = NEW.id)
    BEGIN
      INSERT INTO transaction_categories (txn_id, category_id, assigned_at)
      SELECT NEW.id, c.id, CURRENT_TIMESTAMP
      FROM categories c
      JOIN groups g ON g.id = c.group_id
      WHERE g.name = 'Unclassified' AND c.name = 'Uncategorized'
      LIMIT 1;
    END;
    """,

    # Backfill existing transactions missing category assignment (idempotent).
    """
    INSERT INTO transaction_categories (txn_id, category_id, assigned_at)
    SELECT t.id, c.id, CURRENT_TIMESTAMP
    FROM transactions t
    JOIN groups g ON g.name = 'Unclassified'
    JOIN categories c ON c.group_id = g.id AND c.name = 'Uncategorized'
    LEFT JOIN transaction_categories tc ON tc.txn_id = t.id
    WHERE tc.txn_id IS NULL;
    """,
]

async def apply_schema_bootstrap(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        for stmt in SQL_STATEMENTS:
            await conn.exec_driver_sql(stmt)
