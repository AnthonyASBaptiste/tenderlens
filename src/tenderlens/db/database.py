from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.tenderlens.config import settings
from src.tenderlens.db.models import Base
import os

# Format database URL for SQLAlchemy async if using PostgreSQL
db_url = settings.database_url
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif db_url.startswith("postgresql://") and "+asyncpg" not in db_url:
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

if "sqlite" in db_url:
    db_path = db_url.replace("sqlite+aiosqlite:///", "")
    dir_name = os.path.dirname(db_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

engine = create_async_engine(db_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # If postgres, ensure existing timestamp columns accept timestamptz
        if "postgresql" in str(engine.url):
            from sqlalchemy import text
            try:
                await conn.execute(text("ALTER TABLE contractors ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;"))
                await conn.execute(text("ALTER TABLE tenders ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;"))
                await conn.execute(text("ALTER TABLE tenders ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE;"))
                await conn.execute(text("ALTER TABLE bid_tasks ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;"))
                await conn.execute(text("ALTER TABLE bid_tasks ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE;"))
                await conn.execute(text("ALTER TABLE message_logs ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE;"))
            except Exception:
                pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
