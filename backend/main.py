from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import engine, Base
from imports.schema_bootstrap import apply_schema_bootstrap

# New router import paths (after moving routers into api/routers)
from api.routers.snapshots import router as snapshots_router
from api.routers.transactions import router as transactions_router
from api.routers.taxonomy import router as taxonomy_router
from api.routers.notes import router as notes_router
from api.routers.analytics import router as analytics_router
from api.routers.health import router as health_router



app = FastAPI(title="Gowrox Finance API")

app.include_router(snapshots_router)
app.include_router(transactions_router)
app.include_router(taxonomy_router)
app.include_router(analytics_router)
app.include_router(notes_router)
app.include_router(health_router)

# Allow the frontend to talk to this backend (adjust later if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    # Create database tables if they don't exist yet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_schema_bootstrap(engine)


# Temporary sanity endpoint (can be removed later)
@app.get("/")
async def root():
    return {"status": "ok"}
