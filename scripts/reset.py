from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "silver_safe.db"
BACKUP_DIR = ROOT / "data" / "backups"


BUSINESS_TABLES_DELETE_ORDER = [
    "alert_logs",
    "alerts",
    "locations",
    "trips",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    # Hard safety guard：只允许操作明确的开发数据库文件。
    expected = (ROOT / "data" / "silver_safe.db").resolve()
    actual = DB_PATH.resolve()

    if actual != expected:
        raise SystemExit(f"Refusing unexpected database path: {actual}")

    print(f"Database: {actual}")
    print(f"SHA256 before: {sha256(DB_PATH)}")

    # 每次删除前自动备份。
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"silver_safe-before-reset-{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)

    print(f"Backup created: {backup_path}")

    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON")

        # 先展示删除前数量。
        print("\nBefore reset:")
        for table in BUSINESS_TABLES_DELETE_ORDER:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            print(f"  {table}: {count}")

        answer = input(
            "\nThis will DELETE trips, locations, alerts and alert_logs "
            "from the DEVELOPMENT database.\n"
            "Users/accounts will be preserved.\n"
            "Type RESET to continue: "
        )

        if answer != "RESET":
            print("Cancelled. No data changed.")
            return

        conn.execute("BEGIN")

        for table in BUSINESS_TABLES_DELETE_ORDER:
            conn.execute(f"DELETE FROM {table}")

        conn.commit()

        print("\nAfter reset:")
        for table in BUSINESS_TABLES_DELETE_ORDER:
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]
            print(f"  {table}: {count}")

        print("\nBusiness test data cleaned successfully.")
        print("Preserved: users / elders / family relationships / operators.")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    print(f"SHA256 after:  {sha256(DB_PATH)}")


if __name__ == "__main__":
    main()