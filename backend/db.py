"""Async SQLAlchemy engine + session factory. Single source of truth for DB handle."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings


engine = create_async_engine(settings.db_url, echo=False, future=True)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Create tables if they don't exist. Call on app startup.

    Also runs minimal idempotent migrations for fields added after the
    initial schema (no Alembic — single dev, single SQLite file).
    """
    from backend.memory.models import Base  # noqa: import here to avoid circular

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_profiles_avatar_url)


def _migrate_profiles_avatar_url(sync_conn) -> None:
    """Phase 4.3: add profiles.avatar_url if absent. Safe to run repeatedly —
    SQLite errors with 'duplicate column name' if the column exists; we swallow
    that and leave everything else untouched."""
    try:
        sync_conn.exec_driver_sql("ALTER TABLE profiles ADD COLUMN avatar_url TEXT")
    except Exception:
        pass


async def get_session() -> AsyncSession:
    """FastAPI dependency."""
    async with async_session_factory() as session:
        yield session
