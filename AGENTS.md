# AGENTS.md — Gowrox Finance

## Project overview
This is a personal finance backend API.
The backend is the primary focus.

- Framework: FastAPI (async)
- Database: SQLite
- ORM / access layer: existing code only (do not replace)
- Frontend is out of scope unless explicitly requested.

## How to run
From repo root:

cd backend
python -m uvicorn main:app --port 7712 --reload

## Database rules
- Database file location is defined by existing code
- Do NOT change DB location without asking
- Do NOT drop or recreate tables unless explicitly requested
- Schema changes must be additive and backward-compatible

## API rules
- Follow existing router patterns
- Do NOT rename or remove existing endpoints unless told to do so
- New endpoints must live alongside related routers
- Use Pydantic models consistently
- Return explicit error responses (HTTPException)

## Style constraints
- Small, incremental changes
- Prefer clarity over cleverness
- No speculative refactors
- No new dependencies unless explicitly approved

## When unsure
- Stop and ask instead of guessing