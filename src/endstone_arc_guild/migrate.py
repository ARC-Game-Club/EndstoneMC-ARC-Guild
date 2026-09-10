# -*- coding: utf-8 -*-
"""从 plugins/ARCCore 主库迁移公会四表到本插件库。"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

MIGRATE_FLAG = "migrated.flag"
TABLES: tuple = ("guilds", "guild_members", "guild_invites", "guild_join_requests")


def _detect_core_db(data_dir: Path) -> Optional[Path]:
    """探测弧光核心主库路径。"""
    base = Path("plugins/ARCCore")
    candidates = [
        base / "arc.db",
        base / "arc_core.db",
        base / "data.db",
    ]
    # DATABASE_PATH 常见相对名
    for name in (
        "arc.db",
        "arc_core.db",
        "core.db",
        "data.db",
        "ARCCore.db",
    ):
        candidates.append(base / name)
    seen = set()
    for p in candidates:
        rp = str(p)
        if rp in seen:
            continue
        seen.add(rp)
        if p.is_file():
            return p
    # 任意 .db
    if base.is_dir():
        for p in sorted(base.glob("*.db")):
            if p.is_file():
                return p
    return None


def _core_db_from_settings(setting_manager) -> Optional[Path]:
    try:
        raw = setting_manager.GetSetting("DATABASE_PATH") if setting_manager else None
    except Exception:
        raw = None
    if not raw:
        return None
    p = Path(str(raw))
    if not p.is_absolute():
        p = Path("plugins/ARCCore") / p
    return p if p.is_file() else None


def migrate_from_core(
    target_db_path: Path,
    *,
    core_db_path: Optional[Path] = None,
    setting_manager=None,
    logger=None,
) -> dict:
    """拷贝公会表；返回 {migrated: bool, tables: {name: rows}, error: str}。"""
    result = {"migrated": False, "tables": {}, "error": ""}
    flag = Path(target_db_path).parent / MIGRATE_FLAG
    if flag.exists():
        result["error"] = "already_migrated"
        return result

    core_path = core_db_path or _core_db_from_settings(setting_manager) or _detect_core_db(
        Path(target_db_path).parent
    )
    if not core_path or not Path(core_path).is_file():
        result["error"] = "core_db_not_found"
        return result

    try:
        src = sqlite3.connect(str(core_path))
        src.row_factory = sqlite3.Row
        dst = sqlite3.connect(str(target_db_path))
        try:
            for table in TABLES:
                cols = [
                    r[1]
                    for r in src.execute(f"PRAGMA table_info({table})").fetchall()
                ]
                if not cols:
                    result["tables"][table] = 0
                    continue
                # 目标库先建表（与 GuildSystem 一致的简化结构）
                _ensure_target_table(dst, table)
                rows = src.execute(f"SELECT * FROM {table}").fetchall()  # nosec
                n = 0
                for row in rows:
                    d = {k: row[k] for k in row.keys()}
                    col_names = ", ".join(d.keys())
                    ph = ", ".join("?" * len(d))
                    dst.execute(
                        f"INSERT OR IGNORE INTO {table} ({col_names}) VALUES ({ph})",  # nosec
                        tuple(d.values()),
                    )
                    n += 1
                dst.commit()
                result["tables"][table] = n
            result["migrated"] = True
            flag.write_text("ok\n", encoding="utf-8")
        finally:
            src.close()
            dst.close()
    except Exception as e:
        result["error"] = str(e)
        if logger:
            try:
                logger.error(f"[ARC Guild] migrate error: {e}")
            except Exception:
                pass
    return result


def _ensure_target_table(conn: sqlite3.Connection, table: str) -> None:
    ddl = {
        "guilds": (
            "CREATE TABLE IF NOT EXISTS guilds ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "name TEXT NOT NULL UNIQUE,"
            "owner_xuid TEXT NOT NULL,"
            "created_at TEXT NOT NULL,"
            "motto TEXT DEFAULT '',"
            "size_tier TEXT NOT NULL DEFAULT 'small',"
            "total_contribution INTEGER NOT NULL DEFAULT 0,"
            "join_requires_approval INTEGER NOT NULL DEFAULT 1)"
        ),
        "guild_members": (
            "CREATE TABLE IF NOT EXISTS guild_members ("
            "guild_id INTEGER NOT NULL,"
            "xuid TEXT NOT NULL,"
            "role TEXT NOT NULL,"
            "joined_at TEXT NOT NULL,"
            "contribution INTEGER NOT NULL DEFAULT 0,"
            "PRIMARY KEY (guild_id, xuid),"
            "UNIQUE (xuid))"
        ),
        "guild_invites": (
            "CREATE TABLE IF NOT EXISTS guild_invites ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "guild_id INTEGER NOT NULL,"
            "invitee_xuid TEXT NOT NULL,"
            "inviter_xuid TEXT NOT NULL,"
            "created_at TEXT NOT NULL,"
            "UNIQUE (guild_id, invitee_xuid))"
        ),
        "guild_join_requests": (
            "CREATE TABLE IF NOT EXISTS guild_join_requests ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "guild_id INTEGER NOT NULL,"
            "applicant_xuid TEXT NOT NULL,"
            "created_at TEXT NOT NULL,"
            "UNIQUE (guild_id, applicant_xuid))"
        ),
    }
    conn.execute(ddl[table])
    conn.commit()
