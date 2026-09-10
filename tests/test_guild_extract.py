# -*- coding: utf-8 -*-
import sqlite3
import tempfile
import unittest
from pathlib import Path
import importlib.util
import sys

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


migrate = _load(
    "endstone_arc_guild.migrate",
    _SRC / "endstone_arc_guild" / "migrate.py",
)
economy_bridge = _load(
    "endstone_arc_guild.economy_bridge",
    _SRC / "endstone_arc_guild" / "economy_bridge.py",
)
sync_bridge = _load(
    "endstone_arc_guild.sync_bridge",
    _SRC / "endstone_arc_guild" / "sync_bridge.py",
)


class FakeCore:
    def __init__(self):
        self.synced = []
        self.money = 1000.0
        self.registered = None

    def api_get_player_money(self, xuid=""):
        return self.money

    def api_adjust_player_money(self, xuid="", delta=0.0):
        self.money += float(delta)
        return {"success": True}

    def api_sync_register_namespace(self, plugin_id, tables, on_apply):
        self.registered = (plugin_id, tables, on_apply)
        return {"success": True, "plugin_id": plugin_id}

    def api_sync_unregister_namespace(self, plugin_id):
        return True

    def api_sync_upsert(self, plugin_id, table, row):
        self.synced.append(("upsert", plugin_id, table, row))
        return {"success": True, "synced": True}

    def api_sync_delete(self, plugin_id, table, where, params=None):
        self.synced.append(("delete", plugin_id, table, where, list(params or [])))
        return {"success": True, "synced": True}


class MigrateTests(unittest.TestCase):
    def test_migrate_copies_tables(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            core_db = td / "core.db"
            guild_db = td / "guild.db"
            src = sqlite3.connect(core_db)
            src.execute(
                "CREATE TABLE guilds (id INTEGER PRIMARY KEY, name TEXT, owner_xuid TEXT,"
                " created_at TEXT, motto TEXT, size_tier TEXT, total_contribution INTEGER,"
                " join_requires_approval INTEGER)"
            )
            src.execute(
                "INSERT INTO guilds VALUES (1,'A','x1','t','', 'small',0,1)"
            )
            src.commit()
            src.close()
            r = migrate.migrate_from_core(guild_db, core_db_path=core_db)
            self.assertTrue(r["migrated"], r)
            self.assertEqual(r["tables"].get("guilds"), 1)
            dst = sqlite3.connect(guild_db)
            n = dst.execute("SELECT COUNT(*) FROM guilds").fetchone()[0]
            dst.close()
            self.assertEqual(n, 1)
            # second run skipped
            r2 = migrate.migrate_from_core(guild_db, core_db_path=core_db)
            self.assertFalse(r2["migrated"])
            self.assertEqual(r2["error"], "already_migrated")


class EconomyBridgeTests(unittest.TestCase):
    def test_money_ops(self):
        core = FakeCore()
        b = economy_bridge.EconomyBridge(core)
        self.assertEqual(b.get_player_money_by_xuid("1"), 1000.0)
        self.assertTrue(b.judge_if_player_has_enough_money_by_xuid("1", 500))
        self.assertTrue(b.decrease_player_money_by_xuid("1", 100))
        self.assertEqual(b.get_player_money_by_xuid("1"), 900.0)
        self.assertTrue(b.increase_player_money_by_xuid("1", 50))
        self.assertEqual(b.get_player_money_by_xuid("1"), 950.0)


class SyncBridgeTests(unittest.TestCase):
    def test_register_and_mirror(self):
        core = FakeCore()

        class FakeDB:
            def __init__(self):
                self.rows = {}

            def upsert(self, table, row):
                self.rows.setdefault(table, []).append(dict(row))
                return True

            def delete(self, table, where, params=()):
                return True

            def suppress_write_notify(self):
                from contextlib import nullcontext

                return nullcontext()

        db = FakeDB()
        br = sync_bridge.GuildSyncBridge(db)
        br.set_core(core)
        self.assertTrue(br.register())
        self.assertIsNotNone(core.registered)
        self.assertEqual(core.registered[0], "arc_guild")
        br.mirror_insert("guilds", {"id": 1, "name": "A"})
        self.assertEqual(core.synced[0][0], "upsert")
        # on_apply does not re-mirror
        n = len(core.synced)
        self.assertTrue(br.on_apply("arc_guild", "guilds", "upsert", {"id": 2, "name": "B"}))
        self.assertEqual(len(core.synced), n)
        self.assertEqual(len(db.rows["guilds"]), 1)


if __name__ == "__main__":
    unittest.main()
