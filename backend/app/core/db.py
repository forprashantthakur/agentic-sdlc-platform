from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import log
from app.models import Base

connect_args = {}
if settings.db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.db_url, pool_pre_ping=True, future=True, connect_args=connect_args
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

IS_POSTGRES = engine.dialect.name == "postgresql"


# Schema reconciliation for columns whose type changed after a table already existed.
# create_all() only creates; it never alters. A POC shortcut — a real deployment uses
# Alembic, and this list should shrink to zero the moment it does.
_RECONCILE = [
    "ALTER TABLE approvals ALTER COLUMN token TYPE TEXT",
]


def init_db() -> None:
    if IS_POSTGRES:
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    if IS_POSTGRES:
        for stmt in _RECONCILE:
            try:
                with engine.begin() as conn:
                    conn.execute(text(stmt))
            except Exception as e:  # table may not exist yet on a first boot
                log.warning("db.reconcile_skipped", stmt=stmt, error=str(e))


def get_session() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
