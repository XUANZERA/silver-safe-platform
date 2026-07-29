from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _normalize_database_url(database_url: str) -> str:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url == "sqlite:///:memory:":
        return database_url

    database_path = Path(database_url.removeprefix(prefix))
    if not database_path.is_absolute():
        database_path = (REPOSITORY_ROOT / database_path).resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{database_path.as_posix()}"


database_url = _normalize_database_url(settings.database_url)
engine = create_engine(
    database_url,
    connect_args={"check_same_thread": False, "timeout": 5}
    if database_url.startswith("sqlite")
    else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        if database_url != "sqlite:///:memory:":
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def get_db() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


def init_database() -> None:
    import app.models  # noqa: F401
    from app.services.security_maintenance import prune_expired_security_data
    from app.services.seed import seed_demo_data

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_demo_data(session)
        prune_expired_security_data(session)
