from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import engine, Base

# New router import paths (after moving routers into api/routers)
from api.routers.snapshots import router as snapshots_router
from api.routers.transactions import router as transactions_router
from api.routers.classification import router as classification_router
from api.routers.analytics import router as analytics_router



app = FastAPI(title="Gowrox Finance API")

app.include_router(transactions_router)
app.include_router(snapshots_router)
app.include_router(classification_router)
app.include_router(analytics_router)

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


# Temporary sanity endpoint (can be removed later)
@app.get("/")
async def root():
    return {"status": "ok"}