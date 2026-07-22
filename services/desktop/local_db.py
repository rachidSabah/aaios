"""Local Database Manager — embedded database for offline operation.

Manages a local SQLite database used by the OfflineRuntimeManager,
DesktopPluginLoader, and other desktop services that need persistent storage
without network access. Uses SQLAlchemy with aiosqlite for async operation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.logging import get_logger

_log = get_logger(__name__)


class LocalDatabaseManager:
    """Embedded SQLite database for offline desktop operation."""

    def __init__(self, *, db_dir: str | Path | None = None) -> None:
        self._db_dir = Path(db_dir or "desktop_data/db")
        self._db_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._db_dir / "desktop.db"
        self._engine: Any = None
        self._session_factory: Any = None

    async def open(self) -> None:
        """Open (or create) the local database."""
        try:
            from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

            db_url = f"sqlite+aiosqlite:///{self._db_path}"
            self._engine = create_async_engine(db_url, echo=False)
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            async with self._engine.begin() as conn:
                await conn.run_sync(self._create_tables)
            _log.info("desktop.local_db.opened", path=str(self._db_path))
        except ImportError:
            _log.warning("desktop.local_db.aiosqlite_not_available")
        except Exception as exc:  # noqa: BLE001
            _log.error("desktop.local_db.open_failed", error=str(exc))

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
        _log.info("desktop.local_db.closed")

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def session(self) -> Any:
        if self._session_factory is None:
            raise RuntimeError("LocalDatabaseManager not opened")
        return self._session_factory()

    def _create_tables(self, conn: Any) -> None:
        from sqlalchemy import Column, Integer, MetaData, String, Table, Text

        meta = MetaData()
        Table(
            "offline_cache",
            meta,
            Column("id", Integer, primary_key=True),
            Column("key", String(255), unique=True, nullable=False),
            Column("value", Text, nullable=False),
            Column("created_at", String(32)),
        )
        Table(
            "sync_queue",
            meta,
            Column("id", Integer, primary_key=True),
            Column("action", String(255), nullable=False),
            Column("payload", Text),
            Column("status", String(32), default="pending"),
            Column("retries", Integer, default=0),
            Column("created_at", String(32)),
        )
        Table(
            "desktop_settings",
            meta,
            Column("key", String(255), primary_key=True),
            Column("value", Text),
        )
        meta.create_all(conn)

    def as_dict(self) -> dict[str, Any]:
        return {
            "db_path": str(self._db_path),
            "db_type": "sqlite",
            "open": self._engine is not None,
        }

    async def shutdown(self) -> None:
        await self.close()
