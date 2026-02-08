from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

# Async SQLite connection (relative path)
DATABASE_URL = "sqlite+aiosqlite:///./data/gowrox.db"

# Shared database engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # set True to log SQL
)

# Session factory (one session per request)
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Base class for ORM models
class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:
    """FastAPI dependency that yields a DB session."""
    async with SessionLocal() as session:
        yield session
