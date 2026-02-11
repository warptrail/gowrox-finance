from __future__ import annotations

import re
from datetime import date

import typer

from .api import TidyLedgerApi
from .tui import run_categorizer

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _month_bounds(yyyy_mm: str) -> tuple[date, date]:
    if not _MONTH_RE.match(yyyy_mm):
        raise ValueError("Month must be in YYYY-MM format")

    year = int(yyyy_mm[:4])
    month = int(yyyy_mm[5:7])
    if month < 1 or month > 12:
        raise ValueError("Month must be between 01 and 12")

    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def main(
    base_url: str = typer.Option("http://localhost:7712", "--base-url", help="Backend API base URL"),
    page_limit: int = typer.Option(200, "--page-limit", min=1, max=5000, help="Transactions page size"),
    no_curl: bool = typer.Option(False, "--no-curl", help="Do not print equivalent curl commands"),
) -> None:
    """Human-in-the-loop transaction categorizer for Gowrox backend API."""
    ledger_raw = typer.prompt("Ledger to process (checking|credit)").strip().lower()
    if ledger_raw not in {"checking", "credit"}:
        typer.secho("Invalid ledger. Use 'checking' or 'credit'.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    ledger = ledger_raw
    month = typer.prompt("Month to process (YYYY-MM)").strip()

    try:
        start_date, end_date_exclusive = _month_bounds(month)
    except ValueError as exc:
        typer.secho(f"Invalid month: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    typer.echo(f"Processing ledger={ledger} month={month} ({start_date}..{end_date_exclusive} exclusive)")

    with TidyLedgerApi(base_url=base_url, emit_curl=not no_curl) as api:
        try:
            stats = run_categorizer(
                api=api,
                account=ledger,
                start_date=start_date,
                end_date_exclusive=end_date_exclusive,
                page_limit=page_limit,
            )
        except Exception as exc:  # pragma: no cover - friendly CLI failure path
            typer.secho(f"API/UI error: {exc}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1) from exc

    typer.echo("\nDone.")
    typer.echo(f"Unclassified seen: {stats.processed}")
    typer.echo(f"Classified: {stats.classified}")
    typer.echo(f"Skipped: {stats.skipped}")


if __name__ == "__main__":
    typer.run(main)
