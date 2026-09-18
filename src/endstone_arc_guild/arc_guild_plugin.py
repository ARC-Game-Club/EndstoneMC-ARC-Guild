# -*- coding: utf-8 -*-
"""弧光公会插件：领域逻辑 + UI + 自有库 + 经 arc_core 跨服同步。"""

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from endstone import Player
from endstone.command import Command, CommandSender
from endstone.event import event_handler, PlayerJoinEvent
from endstone.plugin import Plugin

from endstone_arc_guild.DatabaseManager import DatabaseManager
from endstone_arc_guild.GuildSystem import (
    GuildSystem,
    SIZE_TIER_LARGE,
    SIZE_TIER_MEDIUM,
    SIZE_TIER_SMALL,
    SIZE_TIERS,
    strip_mc_color_codes,
)
from endstone_arc_guild.LanguageManager import LanguageManager
from endstone_arc_guild.SettingManager import SettingManager
from endstone_arc_guild.economy_bridge import EconomyBridge
from endstone_arc_guild.guild_menus import GuildMenusMixin
from endstone_arc_guild.migrate import migrate_from_core
from endstone_arc_guild.sync_bridge import GuildSyncBridge

MAIN_PATH = "plugins/ARCGuild"
GUILD_DB = "guild.db"


class ARCGuildPlugin(GuildMenusMixin, Plugin):
    api_version = "0.10"
    name = "arc_guild"

    commands = {
        "arcguild": {
            "description": "打开弧光公会菜单",
            "usages": ["/arcguild"],
            "permissions": ["arc_guild.command.arcguild"],
        },
        "arcguildop": {
            "description": "弧光公会 OP 管理",
            "usages": ["/arcguildop"],
            "permissions": ["arc_guild.command.arcguildop"],
        },
    }

    permissions = {
        "arc_guild.command.arcguild": {
            "description": "Use /arcguild",
            "default": True,
        },
        "arc_guild.command.arcguildop": {
            "description": "Use /arcguildop",
            "default": "op",
        },
    }

    def on_enable(self) -> None:
        self.data_folder.mkdir(parents=True, exist_ok=True)
        self.language_manager = LanguageManager("ZH-CN", base_path=MAIN_PATH)
        self.setting_manager = SettingManager(base_path=MAIN_PATH)
        self.database_manager = DatabaseManager(str(Path(MAIN_PATH) / GUILD_DB))
        self.economy = EconomyBridge()
        self.sync_bridge = GuildSyncBridge(self.database_manager, logger=self.logger)
        self.guild_system = GuildSystem(
            self.database_manager,
            self.setting_manager,
            self.economy,
            logger=self.logger,
        )
        self.guild_system.ensure_tables()

        try:
            mig = migrate_from_core(
                Path(MAIN_PATH) / GUILD_DB,
                setting_manager=self._core_settings_for_migrate(),
                logger=self.logger,
            )
            if mig.get("migrated"):
                self.logger.info(f"[ARC Guild] migrated from core: {mig.get('tables')}")
            elif mig.get("error") not in ("already_migrated", "core_db_not_found"):
                self.logger.warning(f"[ARC Guild] migrate: {mig.get('error')}")
        except Exception as e:
            self.logger.error(f"[ARC Guild] migrate error: {e}")

        self._wire_core()
        self.logger.info("[ARC Guild] enabled")

    def on_disable(self) -> None:
        try:
            self.sync_bridge.unregister()
        except Exception:
            pass
        try:
            core = self._arc_core()
            if core is not None:
                core.api_unregister_main_menu_button("arc_guild:menu")
        except Exception:
            pass
        self.logger.info("[ARC Guild] disabled")

    # ── core bridge ────────────────────────────────────────────────────────
    def _arc_core(self):
        try:
            return self.server.get_plugin("arc_core")
        except Exception:
            return None

    def _core_settings_for_migrate(self):
        try:
            core = self._arc_core()
            return getattr(core, "setting_manager", None)
        except Exception:
            return None

    def _wire_core(self) -> None:
        core = self._arc_core()
        if core is None:
            self.logger.warning("[ARC Guild] arc_core not found; economy/sync disabled")
            return
        self.economy.set_core(core)
        self.sync_bridge.set_core(core)
        self.sync_bridge.set_on_applied(self._on_sync_applied)
        self.sync_bridge.register()

        # 聊天前缀：槽名 guild，priority=2；文本为公会名（无公会则清除）
        try:
            core.api_register_chat_prefix("guild", priority=2)
        except Exception as e:
            self.logger.warning(f"[ARC Guild] register chat prefix failed: {e}")
        # 给当前在线且已入会的玩家补一次前缀
        try:
            for p in list(getattr(self.server, "online_players", []) or []):
                self._set_guild_prefix_for(getattr(p, "xuid", ""))
        except Exception:
            pass

        # 主菜单：公会插件自行注册，核心不再内置
        try:
            core.api_register_main_menu_button(
                "arc_guild:menu",
                self.language_manager.GetText("GUILD_MENU_NAME") or "公会",
                self.show_guild_main_menu,
                priority=7,
                icon="textures/arc_core/guild.png",
            )
        except Exception as e:
            self.logger.warning(f"[ARC Guild] register main menu failed: {e}")

    def _on_sync_applied(self, table: str, op: str, data: dict) -> None:
        """跨服下行后刷新相关前缀（改名/升降级/入退会）。"""
        try:
            if table == "guilds":
                gid = int((data or {}).get("id") or 0) if op != "full" else 0
                if gid > 0:
                    self._refresh_guild_prefix_for_guild(gid)
                else:
                    for p in list(getattr(self.server, "online_players", []) or []):
                        self._set_guild_prefix_for(getattr(p, "xuid", ""))
            elif table == "guild_members":
                xs = str((data or {}).get("xuid") or "")
                if xs:
                    self._refresh_player_name_tag_by_xuid(xs)
        except Exception as e:
            self.logger.warning(f"[ARC Guild] sync applied hook error: {e}")

    # ── UI helpers expected by GuildMenusMixin ─────────────────────────────
    @property
    def land_system(self):
        core = self._arc_core()
        return getattr(core, "land_system", None) if core is not None else None

    def show_main_menu(self, player: Player) -> None:
        core = self._arc_core()
        if core is not None and hasattr(core, "show_main_menu"):
            core.show_main_menu(player)

    def show_op_main_panel(self, player: Player) -> None:
        core = self._arc_core()
        if core is not None and hasattr(core, "show_op_main_panel"):
            core.show_op_main_panel(player)

    def _format_money_display(self, value: float) -> str:
        return self.economy.format_money_display(value)

    def _toast_title(self, key: str, fallback: str) -> str:
        text = self.language_manager.GetText(key)
        title = text if text and str(text).strip() else fallback
        return str(title or "").strip() or fallback

    def _strip_arc_message_prefix(self, message: str) -> str:
        import re

        s = str(message or "").strip()
        if not s:
            return ""
        cleaned = re.sub(r"^(?:§.)*\[弧光(?:核心|公会)\]\s*", "", s)
        return cleaned.strip() if cleaned else s

    def _send_toast(self, player: Player, title: str, content: str = "") -> None:
        if player is None:
            return
        title_s = str(title or "").strip() or "公会"
        content_s = str(content or "").strip()
        try:
            player.send_toast(title_s, content_s)
            return
        except Exception:
            pass
        try:
            if content_s:
                player.send_message(f"{title_s} {content_s}".strip())
            else:
                player.send_message(title_s)
        except Exception:
            pass

    def _notify_important(
        self, player: Player, message: str, *, title: Optional[str] = None
    ) -> None:
        if player is None:
            return
        msg = str(message or "").strip()
        if not msg:
            return
        self._send_toast(
            player,
            title or self._toast_title("TOAST_DEFAULT_TITLE", "公会"),
            self._strip_arc_message_prefix(msg),
        )

    def get_player_name_by_xuid(
        self, xuid: str, return_with_title: bool = False
    ) -> str:
        core = self._arc_core()
        if core is not None:
            try:
                return str(
                    core.api_get_player_name_by_xuid(
                        xuid, with_title=bool(return_with_title)
                    )
                    or ""
                )
            except Exception:
                pass
        p = self._find_online_player_by_xuid(xuid)
        return p.name if p is not None else ""

    def _update_player_name_tag(self, player: Player) -> None:
        self._set_guild_prefix_for(player.xuid)
        core = self._arc_core()
        if core is not None and hasattr(core, "_update_player_name_tag"):
            try:
                core._update_player_name_tag(player)
            except Exception:
                pass

    def _refresh_player_name_tag_by_xuid(self, xuid: Optional[str]) -> None:
        if not xuid:
            return
        self._set_guild_prefix_for(xuid)
        p = self._find_online_player_by_xuid(str(xuid))
        if p is not None:
            self._update_player_name_tag(p)

    def _set_guild_prefix_for(self, xuid: Any) -> None:
        """把公会名写入核心前缀槽 guild；无公会则清除显示。"""
        core = self._arc_core()
        if core is None:
            return
        xuid_s = str(xuid or "").strip()
        if not xuid_s:
            return
        try:
            text = self.build_guild_chat_prefix(xuid_s)
            core.api_set_player_chat_prefix("guild", text, xuid=xuid_s)
        except Exception as e:
            self.logger.warning(f"[ARC Guild] set prefix error: {e}")

    def build_guild_chat_prefix(self, xuid: str) -> str:
        """有公会：带规模色的 [公会名]；无公会/查询失败：空串（清除前缀）。"""
        try:
            mem = self.guild_system.get_membership(str(xuid))
            if not mem:
                return ""
            gid = int(mem.get("guild_id") or 0)
            g = self.guild_system.get_guild(gid)
            if not g:
                return ""
            gname = strip_mc_color_codes(g.get("name")).strip()
            if not gname:
                return ""
            tier = self.guild_system.normalize_size_tier(g.get("size_tier"))
            color = self._guild_size_tier_color(tier)
            return f"{color}[{gname}]§r"
        except Exception:
            return ""

    def _refresh_guild_prefix_for_guild(self, guild_id: int) -> None:
        """公会改名/升降级/成员变动后，刷新该会在线成员前缀。"""
        try:
            for m in self.guild_system.list_members(int(guild_id)) or []:
                self._refresh_player_name_tag_by_xuid(str(m.get("xuid") or ""))
        except Exception as e:
            self.logger.warning(f"[ARC Guild] refresh guild prefixes error: {e}")

    @event_handler
    def on_player_join(self, event: PlayerJoinEvent) -> None:
        try:
            player = event.player
            self.run_player_task(
                player, lambda p: self._set_guild_prefix_for(p.xuid), delay=4
            )
        except Exception:
            pass

    def run_player_task(self, player: Player, fn: Callable[[Player], None], delay: int = 0):
        try:
            if delay and delay > 0:
                return self.server.scheduler.run_task(self, lambda: fn(player), delay=delay)
            return self.server.scheduler.run_task(self, lambda: fn(player))
        except Exception:
            try:
                fn(player)
            except Exception:
                pass

    def delay_teleport_to_land(self, player: Player, land_id: int, position: tuple) -> None:
        core = self._arc_core()
        if core is not None and hasattr(core, "delay_teleport_to_land"):
            core.delay_teleport_to_land(player, land_id, position)
            return
        try:
            dim = self.get_land_dimension(land_id)
            core.api_teleport_player_to(
                player.name, list(position) if position else [0, 64, 0], dimension=dim
            )
        except Exception as e:
            player.send_message(self._guild_text("GUILD_ERR_UNKNOWN", "传送失败。"))
            self.logger.warning(f"[ARC Guild] teleport land error: {e}")

    def get_land_info(self, land_id: int):
        core = self._arc_core()
        if core is None:
            return None
        try:
            return core.api_get_land_info(land_id)
        except Exception:
            return None

    def get_land_teleport_point(self, land_id: int):
        info = self.get_land_info(land_id)
        if not info:
            return None
        try:
            return (
                int(info.get("tp_x") or info.get("x") or 0),
                int(info.get("tp_y") or info.get("y") or 64),
                int(info.get("tp_z") or info.get("z") or 0),
            )
        except Exception:
            return None

    def get_land_dimension(self, land_id: int) -> str:
        info = self.get_land_info(land_id)
        if not info:
            return "minecraft:overworld"
        return str(info.get("dimension") or "minecraft:overworld")

    def get_player_xuid_by_name(self, player_name: str) -> Optional[str]:
        core = self._arc_core()
        if core is not None:
            try:
                return core.api_get_player_xuid_by_name(player_name)
            except Exception:
                pass
        try:
            p = self.server.get_player(player_name)
            return str(p.xuid) if p is not None else None
        except Exception:
            return None

    # ── public API for arc_core soft-deps ─────────────────────────────────
    def api_get_player_guild_id(self, player_name: str = "", xuid: str = "") -> int:
        xs = str(xuid or "").strip()
        if not xs and player_name:
            xs = self.get_player_xuid_by_name(player_name) or ""
        if not xs:
            return 0
        try:
            mem = self.guild_system.get_membership(xs)
            return int(mem.get("guild_id") or 0) if mem else 0
        except Exception:
            return 0

    def api_get_guild_info(self, guild_id: int) -> dict:
        try:
            g = self.guild_system.get_guild(int(guild_id))
            if not g:
                return {}
            return dict(g)
        except Exception:
            return {}

    def api_is_same_guild(self, xuid_a: str, xuid_b: str) -> bool:
        try:
            a = self.guild_system.get_membership(str(xuid_a or ""))
            b = self.guild_system.get_membership(str(xuid_b or ""))
            if not a or not b:
                return False
            return int(a.get("guild_id") or 0) == int(b.get("guild_id") or 0) and int(
                a.get("guild_id") or 0
            ) > 0
        except Exception:
            return False

    def api_get_guild_land_eligibility(self, xuid: str = "", contrib_cost: int = 0) -> dict:
        """核心圈地面板：是否可创建公会领地。失败/无公会返回空或 eligible=False。"""
        from endstone_arc_guild.GuildSystem import ROLE_MANAGER, ROLE_OWNER

        xs = str(xuid or "").strip()
        out = {
            "eligible": False,
            "guild_id": 0,
            "role": "",
            "total_contribution": 0,
            "contrib_cost": int(contrib_cost or 0),
        }
        if not xs:
            return out
        try:
            mem = self.guild_system.get_membership(xs)
            if not mem:
                return out
            gid = int(mem.get("guild_id") or 0)
            if gid <= 0:
                return out
            out["guild_id"] = gid
            out["role"] = str(mem.get("role") or "")
            out["total_contribution"] = int(
                self.guild_system.get_guild_total_contribution(gid) or 0
            )
            cost = int(contrib_cost or 0)
            out["eligible"] = (
                out["role"] in (ROLE_OWNER, ROLE_MANAGER)
                and out["total_contribution"] >= cost > 0
            )
            return out
        except Exception:
            return out

    def api_consume_guild_contribution_for_land(
        self, xuid: str = "", contrib_cost: int = 0
    ) -> dict:
        """扣公会公共贡献以创建领地；成功返回 guild_id/guild_name/new_total。"""
        from endstone_arc_guild.GuildSystem import ROLE_MANAGER, ROLE_OWNER, strip_mc_color_codes

        xs = str(xuid or "").strip()
        cost = int(contrib_cost or 0)
        if not xs or cost <= 0:
            return {"success": False, "error": "GUILD_INVALID_PLAYER"}
        try:
            mem = self.guild_system.get_membership(xs)
            if not mem:
                return {"success": False, "error": "GUILD_NOT_IN_GUILD"}
            role = str(mem.get("role") or "")
            if role not in (ROLE_OWNER, ROLE_MANAGER):
                return {"success": False, "error": "GUILD_NO_PERMISSION"}
            gid = int(mem.get("guild_id") or 0)
            if gid <= 0:
                return {"success": False, "error": "GUILD_NOT_FOUND"}
            ok, err, new_total = self.guild_system.consume_guild_contribution(gid, cost)
            if not ok:
                return {"success": False, "error": err or "GUILD_DB_ERROR"}
            g = self.guild_system.get_guild(gid) or {}
            name = strip_mc_color_codes(g.get("name") or "").strip() or str(gid)
            # 贡献变更需跨服
            try:
                if g:
                    self.sync_bridge.mirror_insert("guilds", dict(g))
            except Exception:
                pass
            return {
                "success": True,
                "guild_id": gid,
                "guild_name": name,
                "new_total": int(new_total or 0),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def api_consume_guild_contribution(self, guild_id: int, points: int) -> dict:
        """按公会 id 扣公共贡献（领地扩建等）；不校验操作者角色。"""
        try:
            ok, err, new_total = self.guild_system.consume_guild_contribution(
                int(guild_id), int(points)
            )
            if ok:
                g = self.guild_system.get_guild(int(guild_id))
                if g:
                    self.sync_bridge.mirror_insert("guilds", dict(g))
            return {
                "success": bool(ok),
                "error": err or "",
                "new_total": int(new_total or 0),
            }
        except Exception as e:
            return {"success": False, "error": str(e), "new_total": 0}

    def api_refund_guild_contribution_pool(self, guild_id: int, points: int) -> bool:
        try:
            ok = bool(self.guild_system.refund_guild_contribution_pool(int(guild_id), int(points)))
            if ok:
                g = self.guild_system.get_guild(int(guild_id))
                if g:
                    self.sync_bridge.mirror_insert("guilds", dict(g))
            return ok
        except Exception:
            return False

    def api_add_guild_contribution(
        self, player_name: str = "", points: int = 0, xuid: str = ""
    ) -> dict:
        xs = str(xuid or "").strip()
        if not xs and player_name:
            xs = self.get_player_xuid_by_name(player_name) or ""
        try:
            ok, err, info = self.guild_system.add_contribution_by_xuid(xs, int(points or 0))
            return {"success": bool(ok), "error": err or "", "info": info or {}}
        except Exception as e:
            return {"success": False, "error": str(e), "info": {}}

    def api_add_personal_guild_contribution(
        self, player_name: str = "", points: int = 0, xuid: str = ""
    ) -> dict:
        """只增加成员私人贡献点（不动公会公共池）；供 arc_hunter 等任务奖励调用。

        返回 {"success": bool, "error": str, "info": {"personal": int, "guild_id": int}}。
        """
        xs = str(xuid or "").strip()
        if not xs and player_name:
            xs = self.get_player_xuid_by_name(player_name) or ""
        info: dict = {"personal": 0, "guild_id": 0}
        if not xs:
            return {"success": False, "error": "GUILD_INVALID_PLAYER", "info": info}
        try:
            mem = self.guild_system.get_membership(xs)
            if not mem:
                return {"success": False, "error": "GUILD_NOT_IN_GUILD", "info": info}
            gid = int(mem.get("guild_id") or 0)
            if gid <= 0:
                return {"success": False, "error": "GUILD_NOT_IN_GUILD", "info": info}
            ok, err, new_personal = self.guild_system.change_member_contribution_in_guild(
                gid, xs, int(points or 0)
            )
            info["guild_id"] = gid
            info["personal"] = int(new_personal or 0)
            return {"success": bool(ok), "error": err or "", "info": info}
        except Exception as e:
            return {"success": False, "error": str(e), "info": info}

    def api_get_player_guild_contribution(self, player_name: str = "", xuid: str = "") -> int:
        xs = str(xuid or "").strip()
        if not xs and player_name:
            xs = self.get_player_xuid_by_name(player_name) or ""
        try:
            return int(self.guild_system.get_member_contribution(xs) or 0)
        except Exception:
            return 0

    def api_list_guild_members(self, guild_id: int) -> list:
        try:
            return list(self.guild_system.list_members(int(guild_id)) or [])
        except Exception:
            return []

    def api_get_guild_lands(self, guild_id: int) -> list:
        core = self._arc_core()
        if core is None:
            return []
        try:
            return core.api_get_guild_lands(guild_id)
        except Exception:
            return []

    # ── commands ───────────────────────────────────────────────────────────
    def on_command(self, sender: CommandSender, command: Command, args: List[str]) -> bool:
        name = (getattr(command, "name", "") or "").lower()
        if name == "arcguild":
            if not isinstance(sender, Player):
                sender.send_message("[ARC Guild] Players only.")
                return True
            self.show_guild_main_menu(sender)
            return True
        if name == "arcguildop":
            if not isinstance(sender, Player):
                sender.send_message("[ARC Guild] Players only.")
                return True
            if not sender.is_op:
                sender.send_message(self._guild_text("GUILD_ERR_NO_PERMISSION", "没有权限。"))
                return True
            self.show_op_guild_manage_panel(sender)
            return True
        return False
