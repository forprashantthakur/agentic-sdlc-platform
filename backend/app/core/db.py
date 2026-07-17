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
    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS context JSONB NOT NULL DEFAULT '{}'::jsonb",
]

# Native Postgres ENUMs are not altered by create_all(). Flow 2 added five ArtifactType values, and
# an existing live database's `artifacttype` enum does not have them — so an INSERT of a Flow-2
# artifact would fail with "invalid input value for enum". ADD VALUE IF NOT EXISTS is idempotent and
# safe to run every boot. It must run in AUTOCOMMIT (not a transaction), which is why it is handled
# separately below.
_ENUM_VALUES = [
    "REFINED_BACKLOG", "GROOMING_PACK", "CODE_REVIEW", "TEST_CASES", "RELEASE_HANDOFF",
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
        # Enum values: ADD VALUE cannot run inside a transaction, so use an autocommit connection.
        for val in _ENUM_VALUES:
            try:
                with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                    conn.execute(text(f"ALTER TYPE artifacttype ADD VALUE IF NOT EXISTS '{val}'"))
            except Exception as e:
                log.warning("db.enum_reconcile_skipped", value=val, error=str(e))


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
