# -*- coding: utf-8 -*-
"""跨服同步桥：本地写后 api_sync_*；下行 on_apply 写回本插件库。"""
from __future__ import annotations

import threading
from typing import Any, Dict, List

NS = "arc_guild"

TABLE_FIELDS: Dict[str, Dict[str, str]] = {
    "guilds": {
        "id": "INTEGER",
        "name": "TEXT",
        "owner_xuid": "TEXT",
        "created_at": "TEXT",
        "motto": "TEXT",
        "size_tier": "TEXT",
        "total_contribution": "INTEGER",
        "join_requires_approval": "INTEGER",
    },
    "guild_members": {
        "guild_id": "INTEGER",
        "xuid": "TEXT",
        "role": "TEXT",
        "joined_at": "TEXT",
        "contribution": "INTEGER",
    },
    "guild_invites": {
        "id": "INTEGER",
        "guild_id": "INTEGER",
        "invitee_xuid": "TEXT",
        "inviter_xuid": "TEXT",
        "created_at": "TEXT",
    },
    "guild_join_requests": {
        "id": "INTEGER",
        "guild_id": "INTEGER",
        "applicant_xuid": "TEXT",
        "created_at": "TEXT",
    },
}

TABLE_PKS: Dict[str, List[str]] = {
    "guilds": ["id"],
    "guild_members": ["guild_id", "xuid"],
    "guild_invites": ["id"],
    "guild_join_requests": ["id"],
}


class GuildSyncBridge:
    """把 GuildSystem 写库动作镜像到 arc_core 插件同步 API。"""

    def __init__(self, db, logger=None):
        self.db = db
        self.logger = logger
        self._core = None
        self._applying = threading.local()
        self._registered = False

    def set_core(self, core) -> None:
        self._core = core

    def _in_apply(self) -> bool:
        return bool(getattr(self._applying, "flag", False))

    def register(self) -> bool:
        core = self._core
        if core is None:
            return False
        tables = {
            t: {"fields": dict(TABLE_FIELDS[t]), "primary_keys": list(TABLE_PKS[t])}
            for t in TABLE_FIELDS
        }
        try:
            r = core.api_sync_register_namespace(NS, tables, self.on_apply)
            self._registered = bool(isinstance(r, dict) and r.get("success"))
            return self._registered
        except Exception as e:
            if self.logger:
                self.logger.error(f"[ARC Guild] sync register failed: {e}")
            return False

    def unregister(self) -> None:
        core = self._core
        if core is None:
            return
        try:
            core.api_sync_unregister_namespace(NS)
        except Exception:
            pass
        self._registered = False

    def on_apply(self, namespace: str, table: str, op: str, data: Dict[str, Any]) -> bool:
        if namespace != NS or table not in TABLE_FIELDS:
            return False
        self._applying.flag = True
        try:
            if op == "full":
                rows = data.get("rows") or []
                ok = True
                for row in rows:
                    if not self._upsert_local(table, row):
                        ok = False
                return ok
            if op == "upsert":
                return self._upsert_local(table, data)
            if op == "delete":
                where = data.get("_where") or ""
                params = tuple(data.get("_params") or [])
                if not where:
                    return False
                return bool(self.db.delete(table, where, params))
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"[ARC Guild] on_apply {table}/{op} error: {e}")
            return False
        finally:
            self._applying.flag = False

    def _upsert_local(self, table: str, row: Dict[str, Any]) -> bool:
        if not row:
            return False
        with self.db.suppress_write_notify():
            return bool(self.db.upsert(table, dict(row)))

    def mirror_insert(self, table: str, row: Dict[str, Any]) -> None:
        if self._in_apply() or not row:
            return
        core = self._core
        if core is None:
            return
        try:
            core.api_sync_upsert(NS, table, dict(row))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[ARC Guild] sync upsert {table}: {e}")

    def mirror_delete(self, table: str, where: str, params) -> None:
        if self._in_apply():
            return
        core = self._core
        if core is None:
            return
        try:
            core.api_sync_delete(NS, table, where, list(params or []))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"[ARC Guild] sync delete {table}: {e}")
