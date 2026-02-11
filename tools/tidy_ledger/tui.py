from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import FuzzyCompleter, WordCompleter

from .api import TidyLedgerApi


@dataclass
class TuiStats:
    processed: int = 0
    classified: int = 0
    skipped: int = 0


UNCLASSIFIED_GROUP_ID = 1
UNCLASSIFIED_CATEGORY_ID = 1


def iter_unclassified(transactions: Iterable[dict], *, end_date_exclusive: date) -> Iterable[dict]:
    end_iso = end_date_exclusive.isoformat()
    for txn in transactions:
        txn_date = str(txn.get("date") or "")
        if txn_date >= end_iso:
            continue
        if txn.get("group_id") == UNCLASSIFIED_GROUP_ID and txn.get("category_id") == UNCLASSIFIED_CATEGORY_ID:
            yield txn


def run_categorizer(
    *,
    api: TidyLedgerApi,
    account: str,
    start_date: date,
    end_date_exclusive: date,
    page_limit: int = 200,
) -> TuiStats:
    categories = api.get_taxonomy()
    labels = [c.label for c in categories]
    label_to_choice = {c.label: c for c in categories}

    completer = FuzzyCompleter(WordCompleter(labels, ignore_case=True, sentence=True, match_middle=True))
    session = PromptSession()

    stats = TuiStats()
    offset = 0

    while True:
        page = api.list_transactions_page(
            account=account,
            start_date=start_date,
            end_date_exclusive=end_date_exclusive,
            limit=page_limit,
            offset=offset,
        )
        if not page:
            break

        for txn in iter_unclassified(page, end_date_exclusive=end_date_exclusive):
            stats.processed += 1
            print("\n---")
            print(f"date: {txn.get('date')}")
            print(f"account: {txn.get('account')}")
            print(f"amount: {txn.get('amount')}")
            print(f"description: {txn.get('description')}")
            print(f"id: {txn.get('id')}")
            print("controls: <enter>=apply  s=skip  q=quit")

            while True:
                raw = session.prompt("category (Group / Category): ", completer=completer).strip()
                if raw.lower() == "s":
                    stats.skipped += 1
                    break
                if raw.lower() == "q":
                    return stats
                if not raw:
                    print("Select a category, or use s/q.")
                    continue

                choice = label_to_choice.get(raw)
                if choice is None:
                    print("No exact match. Use autocomplete and choose a listed value.")
                    continue

                api.assign_transaction_category(int(txn["id"]), choice.category_id)
                stats.classified += 1
                break

        offset += page_limit

    return stats
