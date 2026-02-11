from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


@dataclass(frozen=True)
class CategoryChoice:
    group_id: int
    group_name: str
    category_id: int
    category_name: str

    @property
    def label(self) -> str:
        return f"{self.group_name} / {self.category_name}"


class TidyLedgerApi:
    def __init__(self, base_url: str, timeout: float = 20.0, emit_curl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.emit_curl = emit_curl
        self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "TidyLedgerApi":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _curl(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> str:
        parts = ["curl", "-X", method.upper()]
        if params:
            parts.append("--get")
            for key, value in params.items():
                parts.extend(["--data-urlencode", f"{key}={value}"])
        if json_body is not None:
            parts.extend(["-H", "Content-Type: application/json", "-d", json.dumps(json_body, separators=(",", ":"))])
        parts.append(f"{self.base_url}{path}")
        return " ".join(shlex.quote(p) for p in parts)

    def _print_curl(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> None:
        if self.emit_curl:
            print(self._curl(method=method, path=path, params=params, json_body=json_body))

    def get_taxonomy(self) -> list[CategoryChoice]:
        path = "/api/taxonomy"
        self._print_curl("GET", path)
        resp = self._client.get(path)
        resp.raise_for_status()
        payload = resp.json()

        choices: list[CategoryChoice] = []
        for group in payload:
            for category in group.get("categories", []):
                choices.append(
                    CategoryChoice(
                        group_id=int(group["group_id"]),
                        group_name=str(group["group_name"]),
                        category_id=int(category["category_id"]),
                        category_name=str(category["category_name"]),
                    )
                )
        return choices

    def list_transactions_page(
        self,
        *,
        account: str,
        start_date: date,
        end_date_exclusive: date,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        path = "/api/transactions"
        params = {
            "account": account,
            "start": start_date.isoformat(),
            "end": end_date_exclusive.isoformat(),
            "sort_by": "date",
            "sort_dir": "desc",
            "limit": limit,
            "offset": offset,
        }
        self._print_curl("GET", path, params=params)
        resp = self._client.get(path, params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError("Expected list response from /api/transactions")
        return data

    def assign_transaction_category(self, txn_id: int, category_id: int) -> dict[str, Any]:
        path = f"/api/transactions/{txn_id}/category"
        body = {"category_id": category_id}
        self._print_curl("PATCH", path, json_body=body)
        resp = self._client.patch(path, json=body)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Expected object response from PATCH /api/transactions/{id}/category")
        return data
