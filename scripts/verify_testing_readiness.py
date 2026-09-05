from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
DEVELOPMENT_DATABASE = (ROOT / "data" / "silver_safe.db").resolve()
sys.path.insert(0, str(BACKEND_ROOT))


class ReadinessFailure(RuntimeError):
    pass


def testing_database_path(database_url: str) -> Path:
    try:
        url = make_url(database_url)
    except Exception as exc:
        raise ReadinessFailure(f"DATABASE_URL 无法解析：{exc}") from exc
    if not url.drivername.startswith("sqlite") or not url.database:
        raise ReadinessFailure("DATABASE_URL 必须指向文件型 SQLite 测试数据库")
    if url.database == ":memory:":
        raise ReadinessFailure("DATABASE_URL 不得使用内存数据库")

    path = Path(url.database)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if path == DEVELOPMENT_DATABASE or path.name.lower() == "silver_safe.db":
        raise ReadinessFailure(f"DATABASE_URL 指向受保护的开发数据库：{path}")
    return path


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ReadinessFailure(message)


def main() -> int:
    failures: list[str] = []

    def run(label: str, check: Callable[[], str]) -> None:
        try:
            detail = check()
        except Exception as exc:
            failures.append(f"{label}: {exc}")
            print(f"[FAIL] {label}: {exc}")
        else:
            print(f"[PASS] {label}: {detail}")

    settings_holder: dict[str, object] = {}

    def check_environment() -> str:
        require(
            os.environ.get("APP_ENV", "").strip().lower() == "testing",
            "必须显式设置 APP_ENV=testing",
        )
        require(bool(os.environ.get("DATABASE_URL", "").strip()), "必须显式设置 DATABASE_URL")
        require(
            len(os.environ.get("TEST_ACCOUNT_PASSWORD", "")) >= 8,
            "必须显式设置至少 8 位的 TEST_ACCOUNT_PASSWORD",
        )

        from app.core.config import Settings

        settings = Settings()
        require(settings.app_env.lower() == "testing", "应用解析后的 APP_ENV 不是 testing")
        require(settings.debug is False, "testing 环境不得启用 DEBUG")
        settings_holder["settings"] = settings
        return "testing 环境变量及安全配置有效"

    run("环境变量配置", check_environment)

    if "settings" not in settings_holder:
        print("[BLOCKED] 环境配置无效，已停止所有数据库与 API 检查。")
        print(f"\n[NO-GO] 共 {len(failures)} 个阻塞项。")
        return 1

    settings = settings_holder["settings"]
    database_path_holder: dict[str, Path] = {}

    def check_database_isolation() -> str:
        database_path = testing_database_path(settings.database_url)  # type: ignore[attr-defined]
        require(database_path.exists(), f"测试数据库不存在：{database_path}")
        require(database_path.is_file(), f"测试数据库路径不是文件：{database_path}")
        database_path_holder["path"] = database_path
        return f"独立数据库 {database_path}"

    run("测试数据库独立性", check_database_isolation)
    if "path" not in database_path_holder:
        print("[BLOCKED] 测试数据库不可用，已停止数据与 API 检查。")
        print(f"\n[NO-GO] 共 {len(failures)} 个阻塞项。")
        return 1

    from fastapi.testclient import TestClient

    from app.api.dependencies import get_current_user
    from app.db.session import SessionLocal, database_url
    from app.main import app
    from app.models.elder import Elder, ElderFamilyBinding
    from app.models.geofence import Geofence
    from app.models.trip import Trip
    from app.models.user import User
    from app.services.seed import (
        TEST_GEOFENCE_LATITUDE,
        TEST_GEOFENCE_LONGITUDE,
        TEST_GEOFENCE_RADIUS_METERS,
        VOLUNTEER_TEST_ACCOUNT_COUNT,
        volunteer_test_username,
    )

    expected_usernames = {
        volunteer_test_username(role, number)
        for number in range(1, VOLUNTEER_TEST_ACCOUNT_COUNT + 1)
        for role in ("elder", "family")
    }
    state: dict[str, object] = {}

    def check_accounts_and_bindings() -> str:
        from app.core.security import verify_password

        with SessionLocal() as session:
            users = list(session.scalars(select(User).order_by(User.username)).all())
            elders = list(session.scalars(select(Elder)).all())
            bindings = list(session.scalars(select(ElderFamilyBinding)).all())

        require(len(users) == 20, f"期望恰好 20 个测试用户，实际 {len(users)} 个")
        require(
            {user.username for user in users} == expected_usernames,
            "测试账号集合不完整或含额外账号",
        )
        require(len(elders) == 10, f"期望 10 份老人资料，实际 {len(elders)} 份")
        require(len(bindings) == 10, f"期望 10 条 1:1 绑定，实际 {len(bindings)} 条")

        users_by_name = {user.username: user for user in users}
        elders_by_user_id = {elder.user_id: elder for elder in elders}
        password = settings.test_account_password.get_secret_value()  # type: ignore[attr-defined]
        require(
            all(verify_password(password, user.password_hash) for user in users),
            "至少一个测试账号密码与 TEST_ACCOUNT_PASSWORD 不一致",
        )

        binding_pairs = {(item.elder_id, item.family_user_id) for item in bindings}
        for number in range(1, VOLUNTEER_TEST_ACCOUNT_COUNT + 1):
            elder_user = users_by_name[volunteer_test_username("elder", number)]
            family_user = users_by_name[volunteer_test_username("family", number)]
            require(elder_user.role == "elder", f"{elder_user.username} 角色错误")
            require(family_user.role == "family", f"{family_user.username} 角色错误")
            elder = elders_by_user_id.get(elder_user.id)
            require(elder is not None, f"{elder_user.username} 缺少老人资料")
            require(
                (elder.id, family_user.id) in binding_pairs,  # type: ignore[union-attr]
                f"第 {number:02d} 组绑定缺失",
            )

        state["users_by_name"] = users_by_name
        state["elders_by_user_id"] = elders_by_user_id
        return "10 组账号、老人资料与严格 1:1 绑定完整"

    run("账号与绑定完整性", check_accounts_and_bindings)

    def check_geofences() -> str:
        with SessionLocal() as session:
            geofences = list(session.scalars(select(Geofence)).all())
        require(len(geofences) == 10, f"期望 10 条围栏，实际 {len(geofences)} 条")
        invalid = [
            item.elder_id
            for item in geofences
            if not (
                item.enabled is True
                and item.crs == "WGS84"
                and item.center_latitude == TEST_GEOFENCE_LATITUDE
                and item.center_longitude == TEST_GEOFENCE_LONGITUDE
                and item.radius_meters == TEST_GEOFENCE_RADIUS_METERS
            )
        ]
        require(not invalid, f"围栏字段无效，elder_id={invalid}")
        return "10/10 enabled，WGS84，中心点与 500m 半径有效"

    run("预置电子围栏", check_geofences)

    def check_active_trips() -> str:
        with SessionLocal() as session:
            trips = list(session.scalars(select(Trip).order_by(Trip.elder_id)).all())
        require(len(trips) == 10, f"期望恰好 10 条 Trip，实际 {len(trips)} 条")
        invalid = [trip.id for trip in trips if trip.status != "active" or trip.started_at is None]
        require(not invalid, f"存在非 active 或无 started_at 的 Trip：{invalid}")
        require(
            len({trip.elder_id for trip in trips}) == 10,
            "Trip 未做到每位测试老人恰好一条",
        )
        state["trips_by_elder_id"] = {trip.elder_id: trip for trip in trips}
        return "10/10 active，且每位测试老人恰好一条"

    run("活跃 Trip", check_active_trips)

    def check_cross_account_isolation() -> str:
        require("users_by_name" in state, "账号检查未通过，无法执行越权验证")
        require("trips_by_elder_id" in state, "Trip 检查未通过，无法执行越权验证")
        users_by_name = state["users_by_name"]
        elders_by_user_id = state["elders_by_user_id"]
        trips_by_elder_id = state["trips_by_elder_id"]
        family_1 = users_by_name["family_test_01"]  # type: ignore[index]
        elder_user_1 = users_by_name["elder_test_01"]  # type: ignore[index]
        elder_user_2 = users_by_name["elder_test_02"]  # type: ignore[index]
        elder_1 = elders_by_user_id[elder_user_1.id]  # type: ignore[index,union-attr]
        elder_2 = elders_by_user_id[elder_user_2.id]  # type: ignore[index,union-attr]
        trip_2 = trips_by_elder_id[elder_2.id]  # type: ignore[index,union-attr]

        app.dependency_overrides[get_current_user] = lambda: family_1
        client = TestClient(app, base_url="https://testing.local")
        try:
            own = client.get(f"{settings.api_prefix}/elders/{elder_1.id}/geofence")  # type: ignore[attr-defined,union-attr]
            cross_read = client.get(f"{settings.api_prefix}/elders/{elder_2.id}/geofence")  # type: ignore[attr-defined,union-attr]
            cross_write = client.post(f"{settings.api_prefix}/trips/{trip_2.id}/start")  # type: ignore[attr-defined,union-attr]
        finally:
            client.close()
            app.dependency_overrides.pop(get_current_user, None)

        require(own.status_code == 200, f"family 01 读取绑定老人失败：HTTP {own.status_code}")
        require(
            cross_read.status_code in {403, 404},
            f"family 01 越权读取 elder 02 未被拒绝：HTTP {cross_read.status_code}",
        )
        require(
            cross_write.status_code == 403,
            f"family 01 越权操作 elder 02 Trip 应返回 403，实际 {cross_write.status_code}",
        )
        return "绑定内读取 200；跨绑定读取被隐藏；跨 elder 02 Trip 操作强制 403"

    run("横向防越权隔离", check_cross_account_isolation)

    def check_sqlite_wal() -> str:
        with SessionLocal() as session:
            mode = session.execute(text("PRAGMA journal_mode")).scalar_one()
            foreign_keys = session.execute(text("PRAGMA foreign_keys")).scalar_one()
            user_count = session.scalar(select(func.count(User.id)))
        require(str(mode).lower() == "wal", f"journal_mode 不是 WAL，而是 {mode}")
        require(foreign_keys == 1, "SQLite foreign_keys 未启用")
        require(user_count == 20, "检查期间测试用户数量发生变化")
        return "WAL 与外键约束已启用"

    run("SQLite 运行模式", check_sqlite_wal)

    def check_runtime_database() -> str:
        configured_path = testing_database_path(database_url)
        require(
            configured_path == database_path_holder["path"],
            "应用实际数据库与环境变量 DATABASE_URL 不一致",
        )
        return "应用实际连接与 DATABASE_URL 指向同一测试库"

    run("应用数据库连接一致性", check_runtime_database)

    if failures:
        print(f"\n[NO-GO] 共 {len(failures)} 个阻塞项：")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\n[GO] 所有 P0 测试数据与准入检查均已通过。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReadinessFailure as exc:
        print(f"[FAIL] 准入预检无法完成：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        print(f"[FAIL] 准入预检发生未处理错误：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
