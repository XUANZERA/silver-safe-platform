from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
DEVELOPMENT_DATABASE = (ROOT / "data" / "silver_safe.db").resolve()


def fail(message: str) -> SystemExit:
    return SystemExit(f"[ABORT] {message}")


def resolve_testing_database() -> tuple[str, Path]:
    if os.environ.get("APP_ENV", "").strip().lower() != "testing":
        raise fail("仅允许在显式设置 APP_ENV=testing 时重置测试数据库。")

    raw_database_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_database_url:
        raise fail("必须显式设置 DATABASE_URL，不能依赖开发环境默认值。")

    try:
        url = make_url(raw_database_url)
    except Exception as exc:
        raise fail(f"DATABASE_URL 无法解析：{exc}") from exc
    if not url.drivername.startswith("sqlite") or not url.database:
        raise fail("志愿者测试重置仅支持独立的文件型 SQLite 数据库。")
    if url.database == ":memory:":
        raise fail("禁止对内存数据库执行志愿者测试重置。")

    database_path = Path(url.database)
    if not database_path.is_absolute():
        database_path = ROOT / database_path
    database_path = database_path.resolve()

    if database_path == DEVELOPMENT_DATABASE or database_path.name.lower() == "silver_safe.db":
        raise fail(f"DATABASE_URL 指向受保护的开发数据库：{database_path}")

    normalized_url = url.set(database=database_path.as_posix()).render_as_string(
        hide_password=False
    )
    return normalized_url, database_path


def backup_database(database_path: Path) -> Path | None:
    if not database_path.exists():
        return None

    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = backup_dir / f"{database_path.stem}-before-reset-{timestamp}.db"

    with sqlite3.connect(database_path) as source, sqlite3.connect(backup_path) as target:
        source.backup(target)
    return backup_path


def reset_and_seed(database_url: str, password: str) -> None:
    sys.path.insert(0, str(BACKEND_ROOT))

    import app.models  # noqa: F401
    from app.db.base import Base
    from app.services.seed import seed_volunteer_test_data

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False, "timeout": 5},
        pool_pre_ping=True,
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

    try:
        Base.metadata.create_all(bind=engine)
        with Session(engine) as session:
            try:
                for table in reversed(Base.metadata.sorted_tables):
                    session.execute(table.delete())
                seed_volunteer_test_data(session, password=password)
            except Exception:
                session.rollback()
                raise
    finally:
        engine.dispose()


def main() -> int:
    database_url, database_path = resolve_testing_database()
    password = os.environ.get("TEST_ACCOUNT_PASSWORD", "")
    if len(password) < 8:
        raise fail("必须显式设置至少 8 位的 TEST_ACCOUNT_PASSWORD。")

    database_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = backup_database(database_path)
    print(f"[SAFE] 测试数据库：{database_path}")
    if backup_path is None:
        print("[BACKUP] 数据库尚不存在，无需备份。")
    else:
        print(f"[BACKUP] 已创建一致性备份：{backup_path}")

    reset_and_seed(database_url, password)
    print("[DONE] 测试数据库已重置为 10 组独立志愿者账号基线。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[FAIL] 测试数据库重置失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
