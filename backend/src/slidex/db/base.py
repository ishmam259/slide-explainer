"""SQLAlchemy engine (SQLite, WAL), sessions, and schema versioning."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from ulid import ULID

SCHEMA_VERSION = 1


def new_id() -> str:
    return str(ULID())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


def _enable_sqlite_pragmas(dbapi_conn: Any, _: Any) -> None:
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA busy_timeout=10000")
    cur.close()


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine: Engine = create_engine(
            f"sqlite:///{path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        event.listen(self.engine, "connect", _enable_sqlite_pragmas)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def init(self) -> None:
        from slidex.db import tables  # noqa: F401, PLC0415 — register tables

        Base.metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.execute(
                text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            )
            current = conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar()
            if current is None:
                conn.execute(
                    text("INSERT INTO schema_version (version) VALUES (:v)"), {"v": SCHEMA_VERSION}
                )

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional session: commits on success, rolls back on error."""
        s = self._sessions()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def dispose(self) -> None:
        self.engine.dispose()
