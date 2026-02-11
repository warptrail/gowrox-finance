# tidy-ledger

Local human-in-the-loop transaction categorizer for the existing backend API (`http://localhost:7712`).

- HTTP-only client (no DB access, no backend imports)
- One ledger per run (`checking` or `credit`)
- One month per run (`YYYY-MM`)
- Prompts only for unclassified txns (`group_id=1` and `category_id=1`)
- Autocomplete/fuzzy category picker from `/api/taxonomy`
- Prints equivalent `curl` commands for every API request it makes

## Install

From repo root:

```bash
python3 -m pip install -r tools/tidy_ledger/requirements.txt
```

## Run

From repo root:

```bash
tools/tidy-ledger
```

Optional flags:

```bash
tools/tidy-ledger --base-url http://localhost:7712 --page-limit 200
```

Disable curl logging:

```bash
tools/tidy-ledger --no-curl
```

## Controls

Per unclassified transaction:

- `Enter`: apply selected category
- `s`: skip transaction
- `q`: quit run immediately

## API calls made

- `GET /api/taxonomy` (once at startup)
- `GET /api/transactions` with:
  - `account={checking|credit}`
  - `start=YYYY-MM-01`
  - `end=first day of next month` (exclusive intent)
  - `sort_by=date`
  - `sort_dir=desc`
  - `limit`, `offset` pagination
- `PATCH /api/transactions/{txn_id}/category` with JSON body `{"category_id": <id>}`
