# -*- coding: utf-8 -*-
"""公会 UI（从弧光核心迁出；混入 ARCGuildPlugin）。"""
from typing import Optional
from endstone import Player

from endstone_arc_guild.GuildSystem import (
    ROLE_MANAGER,
    ROLE_MEMBER,
    ROLE_OWNER,
    SIZE_TIER_LARGE,
    SIZE_TIER_MEDIUM,
    SIZE_TIER_SMALL,
    SIZE_TIERS,
    strip_mc_color_codes as guild_strip_mc_color_codes,
)


class GuildMenusMixin:
    def _guild_text(self, key: str, default: str) -> str:
        t = self.language_manager.GetText(key)
        if t is None or not str(t).strip():
            return default
        return str(t)

    def _guild_err(self, code: Optional[str]) -> str:
        if not code:
            return self._guild_text("GUILD_ERR_UNKNOWN", "[弧光核心]操作失败。")
        return self._guild_text(code, f"[弧光核心]操作失败（{code}）。")

    def _find_online_player_by_xuid(self, xuid: str) -> Optional[Player]:
        xuid_s = str(xuid).strip()
        if not xuid_s:
            return None
        try:
            for p in self.server.online_players or []:
                if str(p.xuid) == xuid_s:
                    return p
        except Exception:
            pass
        return None

    def _resolve_online_player(self, xuid: str = "", name: str = "") -> Optional[Player]:
        """从 online_players 重取活对象；不触碰可能已销毁的旧 Player 引用。"""
        xuid_s = str(xuid or "").strip()
        if xuid_s:
            p = self._find_online_player_by_xuid(xuid_s)
            if p is not None:
                return p
        name_s = str(name or "").strip()
        if name_s:
            try:
                return self.server.get_player(name_s)
            except Exception:
                return None
        return None

    def run_player_task(self, player: Player, fn: Callable[[Player], None], delay: int = 0):
        """调度仅对仍在线玩家执行的回调；闭包只存 xuid/name，避免 purecall 崩服。"""
        xuid = str(getattr(player, "xuid", "") or "").strip()
        name = str(getattr(player, "name", "") or "").strip()

        def _wrapped() -> None:
            p = self._resolve_online_player(xuid, name)
            if p is None:
                return
            fn(p)

        return self.server.scheduler.run_task(self, _wrapped, delay=delay)

    def run_two_player_task(
        self,
        player: Player,
        target_player: Player,
        fn: Callable[[Player, Player], None],
        delay: int = 0,
    ):
        """调度需同时解析发起者与目标仍在线的回调。"""
        xuid = str(getattr(player, "xuid", "") or "").strip()
        name = str(getattr(player, "name", "") or "").strip()
        target_xuid = str(getattr(target_player, "xuid", "") or "").strip()
        target_name = str(getattr(target_player, "name", "") or "").strip()

        def _wrapped() -> None:
            p = self._resolve_online_player(xuid, name)
            if p is None:
                return
            t = self._resolve_online_player(target_xuid, target_name)
            if t is None:
                return
            fn(p, t)

        return self.server.scheduler.run_task(self, _wrapped, delay=delay)

    # Guild
    def _guild_size_tier_color(self, tier: str) -> str:
        """规模等级的 MC 颜色码：小型 §h，中型 §s，大型 §p（可由语言文件覆盖）。"""
        t = self.guild_system.normalize_size_tier(tier)
        defaults = {
            SIZE_TIER_SMALL: "§h",
            SIZE_TIER_MEDIUM: "§s",
            SIZE_TIER_LARGE: "§p",
        }
        raw = self._guild_text(f"GUILD_SIZE_TIER_COLOR_{t.upper()}", defaults.get(t, ""))
        s = (raw or "").strip()
        if not s:
            s = defaults.get(t, "")
        return s

    def _guild_size_tier_label(self, tier: str, *, colored: bool = True) -> str:
        """规模等级的本地化显示名。colored=True 时加上 MC 颜色码。"""
        t = self.guild_system.normalize_size_tier(tier)
        plain = self._guild_text(
            f"GUILD_SIZE_TIER_{t.upper()}",
            {SIZE_TIER_SMALL: "小型", SIZE_TIER_MEDIUM: "中型", SIZE_TIER_LARGE: "大型"}.get(
                t, t
            ),
        )
        if not colored:
            return plain
        color = self._guild_size_tier_color(t)
        return f"{color}{plain}§r" if color else plain

    def show_guild_main_menu(self, player: Player):
        xuid = str(player.xuid)
        pending = self.guild_system.list_invites_for_player(xuid)
        mem = self.guild_system.get_membership(xuid)
        cost = self.guild_system.get_create_cost()
        lines = []
        if mem:
            gid = int(mem["guild_id"])
            g = self.guild_system.get_guild(gid)
            gname = g.get("name", "") if g else ""
            role = mem.get("role", "")
            role_label = self._guild_text(
                f"GUILD_ROLE_{str(role).upper()}",
                str(role),
            )
            motto = (g.get("motto") or "") if g else ""
            tier = self.guild_system.get_guild_size_tier(gid)
            tier_label = self._guild_size_tier_label(tier)
            cap = self.guild_system.get_size_tier_max(tier)
            cur = self.guild_system.count_members(gid)
            personal_contrib = self.guild_system.get_member_contribution(xuid)
            guild_contrib = self.guild_system.get_guild_total_contribution(gid)
            lines.append(
                self._guild_text("GUILD_MAIN_IN_GUILD", "所属公会：{0}  职级：{1}").format(
                    gname, role_label
                )
            )
            if motto:
                lines.append(
                    self._guild_text("GUILD_MAIN_MOTTO", "简介：{0}").format(motto)
                )
            lines.append(
                self._guild_text(
                    "GUILD_MAIN_SIZE_LINE",
                    "规模：{0}  人数：{1}/{2}",
                ).format(tier_label, cur, cap)
            )
            lines.append(
                self._guild_text(
                    "GUILD_MAIN_CONTRIB_LINE",
                    "公会贡献点：{0}  我的贡献点：{1}",
                ).format(int(guild_contrib), int(personal_contrib))
            )
        else:
            lines.append(
                self._guild_text(
                    "GUILD_MAIN_NOT_IN_GUILD",
                    "您尚未加入公会。创建需支付 {0}。",
                ).format(self._format_money_display(cost))
            )
            small_max = self.guild_system.get_size_tier_max(SIZE_TIER_SMALL)
            medium_max = self.guild_system.get_size_tier_max(SIZE_TIER_MEDIUM)
            large_max = self.guild_system.get_size_tier_max(SIZE_TIER_LARGE)
            lines.append(
                self._guild_text(
                    "GUILD_MAIN_TIER_HINT",
                    "公会规模：小型≤{0} / 中型≤{1} / 大型≤{2}（默认小型，由 OP 升级）",
                ).format(small_max, medium_max, large_max)
            )
        if pending:
            lines.append(
                self._guild_text(
                    "GUILD_MAIN_PENDING_HINT",
                    "您有 {0} 条待处理公会邀请。",
                ).format(len(pending))
            )
        form = ActionForm(
            title=self._guild_text("GUILD_MAIN_TITLE", "公会"),
            content="\n".join(lines),
            on_close=None,
        )
        if pending:
            form.add_button(
                self._guild_text("GUILD_BTN_PENDING_INVITES", "待处理邀请"),
                on_click=self.show_guild_pending_invites_menu,
            )
        if not mem:
            form.add_button(
                self._guild_text("GUILD_BTN_CREATE", "创建公会"),
                on_click=self.show_guild_create_panel,
            )
        if mem:
            form.add_button(
                self._guild_text("GUILD_BTN_MY_GUILD", "我的公会"),
                on_click=self.show_guild_my_menu,
            )
        form.add_button(
            self._guild_text("GUILD_BTN_BROWSE_ALL", "查看全部公会"),
            on_click=self.show_guild_browse_menu,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_main_menu,
        )
        player.send_form(form)

    def show_guild_browse_menu(
        self,
        player: Player,
        *,
        page: int = 0,
        name_query: str = "",
    ):
        q = str(name_query or "").strip()
        all_rows = self.guild_system.list_guilds_directory(q)
        page = max(0, int(page))
        ps = GUILD_BROWSE_PAGE_SIZE
        total = len(all_rows)
        total_pages = max(1, (total + ps - 1) // ps)
        if page >= total_pages:
            page = total_pages - 1
        chunk = all_rows[page * ps : (page + 1) * ps]
        hint = self._guild_text(
            "GUILD_BROWSE_HINT",
            "按规模（大→小）排序，同规模按公共贡献点从高到低。",
        )
        filter_line = self._guild_text("GUILD_BROWSE_FILTER", "名称筛选：{0}").format(
            q or self._guild_text("GUILD_BROWSE_NO_FILTER", "（全部）")
        )
        page_line = self._guild_text(
            "GUILD_BROWSE_PAGE",
            "第 {0}/{1} 页，共 {2} 个公会",
        ).format(page + 1, total_pages, total)
        form = ActionForm(
            title=self._guild_text("GUILD_BROWSE_TITLE", "全部公会"),
            content="\n".join([hint, filter_line, page_line]),
            on_close=None,
        )

        def _search(p: Player):
            self.show_guild_browse_search_modal(p, page=page, name_query=q)

        form.add_button(
            self._guild_text("GUILD_BROWSE_BTN_SEARCH", "搜索公会"),
            on_click=_search,
        )
        for row in chunk:
            gid = int(row.get("id") or 0)
            if gid <= 0:
                continue
            gname = str(row.get("name") or "")
            tier = self.guild_system.normalize_size_tier(row.get("size_tier"))
            cap = self.guild_system.get_size_tier_max(tier)
            mc = int(row.get("member_count") or 0)
            contrib = int(row.get("total_contribution") or 0)
            btn = self._guild_text(
                "GUILD_BROWSE_ROW",
                "{0} | {1} {2}/{3} | 贡献 {4}",
            ).format(
                gname,
                self._guild_size_tier_label(tier, colored=False),
                mc,
                cap,
                contrib,
            )

            def _open(p: Player, _gid: int = gid):
                self.show_guild_public_detail(
                    p, _gid, browse_page=page, browse_query=q
                )

            form.add_button(btn, on_click=_open)
        if not chunk and total == 0:
            form.add_button(
                self._guild_text("GUILD_BROWSE_EMPTY", "没有匹配的公会"),
                on_click=lambda p: self.show_guild_browse_menu(
                    p, page=0, name_query=""
                ),
            )
        if page > 0:

            def _prev(p: Player):
                self.show_guild_browse_menu(p, page=page - 1, name_query=q)

            form.add_button(
                self._guild_text("GUILD_BROWSE_PREV", "上一页"),
                on_click=_prev,
            )
        if page < total_pages - 1:

            def _next(p: Player):
                self.show_guild_browse_menu(p, page=page + 1, name_query=q)

            form.add_button(
                self._guild_text("GUILD_BROWSE_NEXT", "下一页"),
                on_click=_next,
            )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_main_menu,
        )
        player.send_form(form)

    def show_guild_browse_search_modal(
        self, player: Player, *, page: int = 0, name_query: str = ""
    ):
        hint = Label(
            text=self._guild_text(
                "GUILD_BROWSE_SEARCH_HINT",
                "输入公会名称关键字（留空列出全部）；匹配不区分大小写。",
            )
        )
        inp = TextInput(
            label=self._guild_text("GUILD_BROWSE_SEARCH_LABEL", "关键字"),
            placeholder=self._guild_text(
                "GUILD_BROWSE_SEARCH_PLACEHOLDER", "例如：星辰"
            ),
            default_value=str(name_query or ""),
        )

        def _submit(p: Player, json_str: str):
            try:
                data = json.loads(json_str)
            except Exception:
                self.show_guild_browse_menu(p, page=0, name_query=name_query)
                return
            if self._modal_choice_is_back(data, 0):
                self.show_guild_browse_menu(p, page=page, name_query=name_query)
                return
            kw = str(data[2]).strip() if len(data) > 2 else ""
            self.show_guild_browse_menu(p, page=0, name_query=kw)

        form = ModalForm(
            title=self._guild_text("GUILD_BROWSE_SEARCH_TITLE", "搜索公会"),
            controls=[self._modal_nav_dropdown(), hint, inp],
            on_close=None,
            on_submit=_submit,
        )
        player.send_form(form)

    def show_guild_public_detail(
        self,
        player: Player,
        guild_id: int,
        *,
        browse_page: int = 0,
        browse_query: str = "",
    ):
        g = self.guild_system.get_guild(int(guild_id))
        if not g:
            player.send_message(self._guild_err("GUILD_NOT_FOUND"))
            self.show_guild_browse_menu(
                player, page=browse_page, name_query=browse_query
            )
            return
        gid = int(g.get("id") or guild_id)
        gname = str(g.get("name") or "")
        motto = str(g.get("motto") or "").strip()
        tier = self.guild_system.get_guild_size_tier(gid)
        cap = self.guild_system.get_size_tier_max(tier)
        cur = self.guild_system.count_members(gid)
        guild_contrib = self.guild_system.get_guild_total_contribution(gid)
        join_req = self.guild_system.guild_join_requires_approval(gid)
        policy_line = (
            self._guild_text("GUILD_PUBLIC_POLICY_APPROVAL", "入会：需管理员审核")
            if join_req
            else self._guild_text("GUILD_PUBLIC_POLICY_OPEN", "入会：未满时可立即加入")
        )
        lines = [
            self._guild_text("GUILD_PUBLIC_NAME", "公会：{0}").format(gname),
            policy_line,
        ]
        if motto:
            lines.append(
                self._guild_text("GUILD_MAIN_MOTTO", "简介：{0}").format(motto)
            )
        lines.append(
            self._guild_text(
                "GUILD_PUBLIC_META",
                "规模：{0}  人数：{1}/{2}\n公共贡献点：{3}",
            ).format(
                self._guild_size_tier_label(tier), cur, cap, int(guild_contrib)
            ),
        )
        viewer_mem = self.guild_system.get_membership(str(player.xuid))
        in_this = bool(
            viewer_mem and int(viewer_mem.get("guild_id") or 0) == gid
        )
        other_guild = bool(
            viewer_mem and int(viewer_mem.get("guild_id") or 0) != gid
        )
        if other_guild:
            og = self.guild_system.get_guild(int(viewer_mem["guild_id"]))
            oname = str(og.get("name") or "") if og else ""
            lines.append(
                self._guild_text(
                    "GUILD_PUBLIC_YOU_IN_OTHER",
                    "您已加入其他公会：{0}",
                ).format(oname)
            )

        def _back(p: Player):
            self.show_guild_browse_menu(
                p, page=browse_page, name_query=browse_query
            )

        form = ActionForm(
            title=self._guild_text("GUILD_PUBLIC_PREVIEW_TITLE", "公会预览"),
            content="\n".join(lines),
            on_close=None,
        )
        if not viewer_mem:
            join_label = (
                self._guild_text("GUILD_PUBLIC_BTN_APPLY", "申请加入")
                if join_req
                else self._guild_text("GUILD_PUBLIC_BTN_JOIN", "加入公会")
            )

            def _join(p: Player, _gid: int = gid):
                ok, err, outcome = self.guild_system.try_public_join_guild(
                    str(p.xuid), _gid
                )
                if ok:
                    if outcome == "joined":
                        p.send_message(
                            self._guild_text(
                                "GUILD_PUBLIC_JOIN_OK",
                                "[弧光核心]已成功加入该公会。",
                            )
                        )
                        self._update_player_name_tag(p)
                    elif outcome == "pending":
                        p.send_message(
                            self._guild_text(
                                "GUILD_PUBLIC_APPLY_SENT",
                                "[弧光核心]已提交入会申请，请等待管理员处理。",
                            )
                        )
                    self.show_guild_main_menu(p)
                else:
                    p.send_message(self._guild_err(err))
                    self.show_guild_public_detail(
                        p,
                        _gid,
                        browse_page=browse_page,
                        browse_query=browse_query,
                    )

            form.add_button(join_label, on_click=_join)
        elif other_guild:
            pass
        elif in_this:
            form.add_button(
                self._guild_text("GUILD_PUBLIC_BTN_MY_GUILD", "我的公会"),
                on_click=self.show_guild_my_menu,
            )
        form.add_button(
            self._guild_text("GUILD_BROWSE_BACK_TO_LIST", "返回列表"),
            on_click=_back,
        )
        player.send_form(form)

    def show_guild_join_policy_menu(
        self,
        player: Player,
        *,
        browse_page: int = 0,
        browse_query: str = "",
        from_my_guild: bool = False,
    ):
        mem = self.guild_system.get_membership(str(player.xuid))
        if not mem or str(mem.get("role") or "") not in (
            ROLE_OWNER,
            ROLE_MANAGER,
        ):
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            if from_my_guild:
                self.show_guild_my_menu(player)
            else:
                self.show_guild_browse_menu(
                    player, page=browse_page, name_query=browse_query
                )
            return
        gid = int(mem["guild_id"])

        def _back_from_policy(p: Player, _gid: int = gid):
            if from_my_guild:
                self.show_guild_my_menu(p)
            else:
                self.show_guild_public_detail(
                    p, _gid, browse_page=browse_page, browse_query=browse_query
                )

        cur = self.guild_system.guild_join_requires_approval(gid)
        desc = self._guild_text(
            "GUILD_POLICY_CURRENT_APPROVAL",
            "当前：新玩家入会需管理员在「入会申请」中审批。",
        )
        if not cur:
            desc = self._guild_text(
                "GUILD_POLICY_CURRENT_OPEN",
                "当前：未满员时，玩家可从「全部公会」中直接加入。",
            )
        form = ActionForm(
            title=self._guild_text("GUILD_POLICY_TITLE", "入会审核"),
            content=desc,
            on_close=None,
        )

        def _set(p: Player, requires: bool):
            ok, err = self.guild_system.set_guild_join_requires_approval(
                str(p.xuid), requires
            )
            if ok:
                p.send_message(
                    self._guild_text(
                        "GUILD_POLICY_OK",
                        "[弧光核心]入会条件已更新。",
                    )
                )
            else:
                p.send_message(self._guild_err(err))
            _back_from_policy(p, gid)

        form.add_button(
            self._guild_text("GUILD_POLICY_BTN_NEED_APPROVAL", "开启：需要审核"),
            on_click=lambda p: _set(p, True),
        )
        form.add_button(
            self._guild_text("GUILD_POLICY_BTN_DIRECT", "关闭：无需审核（可直接加入）"),
            on_click=lambda p: _set(p, False),
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=_back_from_policy,
        )
        player.send_form(form)

    def show_guild_join_requests_menu(self, player: Player):
        mem = self.guild_system.get_membership(str(player.xuid))
        if not mem or str(mem.get("role") or "") not in (
            ROLE_OWNER,
            ROLE_MANAGER,
        ):
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(player)
            return
        gid = int(mem["guild_id"])
        rows = self.guild_system.list_join_requests(gid)
        form = ActionForm(
            title=self._guild_text("GUILD_REQUESTS_TITLE", "入会申请"),
            content=self._guild_text(
                "GUILD_REQUESTS_CONTENT", "选择一名申请人进行处理。"
            ),
            on_close=None,
        )
        if not rows:
            form.add_button(
                self._guild_text("GUILD_REQUESTS_EMPTY", "暂无申请"),
                on_click=self.show_guild_my_menu,
            )
        for r in rows:
            rid = int(r.get("id") or 0)
            ax = str(r.get("applicant_xuid") or "")
            disp = self.get_player_name_by_xuid(ax, return_with_title=False) or ax

            def _open(p: Player, _rid: int = rid):
                self.show_guild_join_request_actions(p, _rid)

            form.add_button(
                self._guild_text("GUILD_REQUESTS_ROW", "{0}").format(disp),
                on_click=_open,
            )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_join_request_actions(self, player: Player, request_id: int):
        mem = self.guild_system.get_membership(str(player.xuid))
        if not mem or str(mem.get("role") or "") not in (
            ROLE_OWNER,
            ROLE_MANAGER,
        ):
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(player)
            return
        req = self.guild_system.get_join_request(int(request_id))
        if not req or int(req.get("guild_id") or 0) != int(mem["guild_id"]):
            player.send_message(
                self._guild_err("GUILD_JOIN_REQUEST_NOT_FOUND")
            )
            self.show_guild_join_requests_menu(player)
            return
        ax = str(req.get("applicant_xuid") or "")
        disp = self.get_player_name_by_xuid(ax, return_with_title=False) or ax
        form = ActionForm(
            title=self._guild_text("GUILD_REQUEST_ACTION_TITLE", "处理申请"),
            content=self._guild_text(
                "GUILD_REQUEST_ACTION_CONTENT", "申请人：{0}"
            ).format(disp),
            on_close=None,
        )

        def _approve(p: Player, _rid: int = int(request_id)):
            ok, err = self.guild_system.approve_join_request(str(p.xuid), _rid)
            if ok:
                p.send_message(
                    self._guild_text(
                        "GUILD_REQUEST_APPROVE_OK",
                        "[弧光核心]已同意该玩家的入会申请。",
                    )
                )
                tgt = self._find_online_player_by_xuid(ax)
                if tgt:
                    tgt.send_message(
                        self._guild_text(
                            "GUILD_REQUEST_ACCEPTED_TARGET",
                            "[弧光核心]您的公会加入申请已通过。",
                        )
                    )
                    self._update_player_name_tag(tgt)
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_join_requests_menu(p)

        def _reject(p: Player, _rid: int = int(request_id)):
            ok, err = self.guild_system.reject_join_request(str(p.xuid), _rid)
            if ok:
                p.send_message(
                    self._guild_text(
                        "GUILD_REQUEST_REJECT_OK",
                        "[弧光核心]已拒绝该申请。",
                    )
                )
                tgt = self._find_online_player_by_xuid(ax)
                if tgt:
                    tgt.send_message(
                        self._guild_text(
                            "GUILD_REQUEST_REJECTED_TARGET",
                            "[弧光核心]您的公会加入申请未通过。",
                        )
                    )
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_join_requests_menu(p)

        form.add_button(
            self._guild_text("GUILD_REQUEST_APPROVE", "同意"),
            on_click=_approve,
        )
        form.add_button(
            self._guild_text("GUILD_REQUEST_REJECT", "拒绝"),
            on_click=_reject,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_join_requests_menu,
        )
        player.send_form(form)

    def show_guild_pending_invites_menu(self, player: Player):
        xuid = str(player.xuid)
        rows = self.guild_system.list_invites_for_player(xuid)
        form = ActionForm(
            title=self._guild_text("GUILD_PENDING_TITLE", "公会邀请"),
            content=self._guild_text("GUILD_PENDING_CONTENT", "选择一条邀请查看详情。"),
            on_close=None,
        )
        for r in rows:
            gid = int(r["guild_id"])
            inv_id = int(r["invite_id"])
            gname = str(r.get("guild_name") or "")
            label = self._guild_text("GUILD_PENDING_ROW", "{0}").format(gname)

            def _open(p: Player, iid: int = inv_id):
                self.show_guild_invite_action_menu(p, iid)

            form.add_button(label, on_click=_open)
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_main_menu,
        )
        player.send_form(form)

    def show_guild_invite_action_menu(self, player: Player, invite_id: int):
        xuid = str(player.xuid)
        inv = self.guild_system.get_invite(invite_id)
        if not inv or str(inv.get("invitee_xuid")) != xuid:
            player.send_message(self._guild_err("GUILD_NO_INVITE"))
            self.show_guild_pending_invites_menu(player)
            return
        g = self.guild_system.get_guild(int(inv["guild_id"]))
        gname = g.get("name", "") if g else ""
        form = ActionForm(
            title=self._guild_text("GUILD_INVITE_DETAIL_TITLE", "邀请详情"),
            content=self._guild_text(
                "GUILD_INVITE_DETAIL_CONTENT", "公会：{0}"
            ).format(gname),
            on_close=None,
        )

        def _accept(p: Player, iid: int = invite_id):
            ok, err = self.guild_system.accept_invite(str(p.xuid), iid)
            if ok:
                p.send_message(
                    self._guild_text("GUILD_ACCEPT_OK", "[弧光核心]已加入公会。")
                )
                self._update_player_name_tag(p)
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_main_menu(p)

        def _decline(p: Player, iid: int = invite_id):
            ok, err = self.guild_system.decline_invite(str(p.xuid), iid)
            if ok:
                p.send_message(
                    self._guild_text("GUILD_DECLINE_OK", "[弧光核心]已拒绝邀请。")
                )
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_pending_invites_menu(p)

        form.add_button(
            self._guild_text("GUILD_INVITE_ACCEPT", "接受"),
            on_click=_accept,
        )
        form.add_button(
            self._guild_text("GUILD_INVITE_DECLINE", "拒绝"),
            on_click=_decline,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_pending_invites_menu,
        )
        player.send_form(form)

    def show_guild_invite_popup_live(
        self, player: Player, guild_id: int, inviter_xuid: str
    ):
        """在线邀请弹窗：不依赖 guild_invites 表，凭公会 id 与邀请人 xuid 确认后加入。"""
        g = self.guild_system.get_guild(int(guild_id))
        if not g:
            return
        gname = str(g.get("name") or "")
        ix = str(inviter_xuid or "").strip()
        inviter_disp = self.get_player_name_by_xuid(ix, return_with_title=False) or ix
        form = ActionForm(
            title=self._guild_text("GUILD_INVITE_POPUP_TITLE", "公会邀请"),
            content=self._guild_text(
                "GUILD_INVITE_POPUP_CONTENT",
                "公会：{0}\n邀请人：{1}\n\n是否加入该公会？",
            ).format(gname, inviter_disp),
            on_close=None,
        )

        def _accept(p: Player, gid: int = int(guild_id), inv: str = ix):
            ok, err = self.guild_system.join_via_live_invite(str(p.xuid), gid, inv)
            if ok:
                p.send_message(
                    self._guild_text("GUILD_ACCEPT_OK", "[弧光核心]已加入公会。")
                )
                self._update_player_name_tag(p)
            else:
                p.send_message(self._guild_err(err))

        def _decline(p: Player):
            p.send_message(
                self._guild_text("GUILD_DECLINE_OK", "[弧光核心]已拒绝邀请。")
            )

        form.add_button(
            self._guild_text("GUILD_INVITE_ACCEPT", "接受"),
            on_click=_accept,
        )
        form.add_button(
            self._guild_text("GUILD_INVITE_DECLINE", "拒绝"),
            on_click=_decline,
        )
        player.send_form(form)

    def _guild_send_live_invite(
        self, inviter: Player, target: Player, guild_id: int
    ) -> None:
        mem = self.guild_system.get_membership(str(inviter.xuid))
        if not mem or int(mem["guild_id"]) != int(guild_id):
            inviter.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(inviter)
            return
        if mem.get("role") not in (ROLE_OWNER, ROLE_MANAGER):
            inviter.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(inviter)
            return
        if self.guild_system.get_membership(str(target.xuid)):
            inviter.send_message(self._guild_err("GUILD_TARGET_IN_GUILD"))
            self.show_guild_invite_online_pick_menu(inviter)
            return
        if self.guild_system.is_guild_full(int(guild_id)):
            inviter.send_message(self._guild_err("GUILD_FULL"))
            self.show_guild_my_menu(inviter)
            return
        self.show_guild_invite_popup_live(
            target, int(guild_id), str(inviter.xuid)
        )
        inviter.send_message(
            self._guild_text(
                "GUILD_INVITE_SENT",
                "[弧光核心]已向 {0} 发送公会邀请。",
            ).format(target.name or "?")
        )
        self.show_guild_my_menu(inviter)

    def show_guild_create_panel(self, player: Player):
        cost = self.guild_system.get_create_cost()
        info = Label(
            text=self._guild_text(
                "GUILD_CREATE_LABEL",
                "创建费用：{0}（将立即扣除）",
            ).format(self._format_money_display(cost))
        )
        name_in = TextInput(
            label=self._guild_text(
                "GUILD_CREATE_NAME_LABEL",
                "公会名称（最多8字；禁止 [ ] \" 与 § 颜色/样式符号）",
            ),
            placeholder=self._guild_text(
                "GUILD_CREATE_NAME_PLACEHOLDER", "请输入唯一公会名"
            ),
        )
        motto_in = TextInput(
            label=self._guild_text("GUILD_CREATE_MOTTO_LABEL", "公会简介（可选）"),
            placeholder=self._guild_text("GUILD_CREATE_MOTTO_PLACEHOLDER", "简介"),
            default_value="",
        )

        def _submit(p: Player, json_str: str):
            try:
                data = json.loads(json_str)
            except Exception:
                p.send_message(
                    self._guild_text("GUILD_CREATE_INVALID", "[弧光核心]输入无效。")
                )
                self.show_guild_create_panel(p)
                return
            if len(data) < 3:
                self.show_guild_create_panel(p)
                return
            name = str(data[1]).strip()
            motto = str(data[2]).strip()
            ok, err = self.guild_system.create_guild(name, str(p.xuid), motto)
            if ok:
                self._notify_important(
                    p,
                    self._guild_text(
                        "GUILD_CREATE_OK",
                        "[弧光核心]公会创建成功，已扣除 {0}。",
                    ).format(self._format_money_display(cost)),
                    title=self._toast_title("GUILD_TOAST_TITLE", "公会"),
                )
                self._update_player_name_tag(p)
                self.show_guild_main_menu(p)
            else:
                p.send_message(self._guild_err(err))
                self.show_guild_create_panel(p)

        form = ModalForm(
            title=self._guild_text("GUILD_CREATE_TITLE", "创建公会"),
            controls=[info, name_in, motto_in],
            on_close=None,
            on_submit=_submit,
        )
        player.send_form(form)

    def show_guild_my_menu(self, player: Player):
        xuid = str(player.xuid)
        mem = self.guild_system.get_membership(xuid)
        if not mem:
            self.show_guild_main_menu(player)
            return
        gid = int(mem["guild_id"])
        role = str(mem.get("role") or "")
        tier = self.guild_system.get_guild_size_tier(gid)
        cap = self.guild_system.get_size_tier_max(tier)
        cur = self.guild_system.count_members(gid)
        personal_contrib = self.guild_system.get_member_contribution(xuid)
        guild_contrib = self.guild_system.get_guild_total_contribution(gid)
        my_content_lines = [
            self._guild_text("GUILD_MY_CONTENT", "管理公会事务。"),
            self._guild_text(
                "GUILD_MY_SIZE_LINE",
                "规模：{0}  人数：{1}/{2}",
            ).format(self._guild_size_tier_label(tier), cur, cap),
            self._guild_text(
                "GUILD_MY_CONTRIB_LINE",
                "公会贡献点：{0}  我的贡献点：{1}",
            ).format(int(guild_contrib), int(personal_contrib)),
        ]
        form = ActionForm(
            title=self._guild_text("GUILD_MY_TITLE", "我的公会"),
            content="\n".join(my_content_lines),
            on_close=None,
        )
        form.add_button(
            self._guild_text("GUILD_BTN_MEMBER_LIST", "成员列表"),
            on_click=lambda p: self.show_guild_member_list_menu(p, readonly=True),
        )
        form.add_button(
            self._guild_text("GUILD_BTN_GUILD_LANDS", "公会领地"),
            on_click=self.show_guild_lands_menu,
        )
        if role in (ROLE_OWNER, ROLE_MANAGER):
            form.add_button(
                self._guild_text("GUILD_BTN_INVITE", "邀请玩家"),
                on_click=self.show_guild_invite_online_pick_menu,
            )
            n_req = self.guild_system.count_join_requests(gid)
            if n_req > 0:
                form.add_button(
                    self._guild_text(
                        "GUILD_BTN_JOIN_REQUESTS", "入会申请 ({0})"
                    ).format(n_req),
                    on_click=self.show_guild_join_requests_menu,
                )
            form.add_button(
                self._guild_text("GUILD_BTN_JOIN_POLICY", "入会审核设置"),
                on_click=lambda p: self.show_guild_join_policy_menu(
                    p, from_my_guild=True
                ),
            )
            form.add_button(
                self._guild_text("GUILD_BTN_KICK", "踢出成员"),
                on_click=self.show_guild_kick_menu,
            )
            if tier != SIZE_TIER_LARGE:
                form.add_button(
                    self._guild_text("GUILD_BTN_UPGRADE_TIER", "升级公会规模"),
                    on_click=self.show_guild_upgrade_tier_menu,
                )
        if role == ROLE_OWNER:
            form.add_button(
                self._guild_text("GUILD_BTN_SET_ROLE", "变更职级"),
                on_click=self.show_guild_set_role_pick_member,
            )
            form.add_button(
                self._guild_text("GUILD_BTN_RENAME", "公会改名"),
                on_click=self.show_guild_rename_panel,
            )
            form.add_button(
                self._guild_text("GUILD_BTN_DISBAND", "解散公会"),
                on_click=self.show_guild_disband_confirm,
            )
        if role != ROLE_OWNER:
            form.add_button(
                self._guild_text("GUILD_BTN_LEAVE", "退出公会"),
                on_click=self.show_guild_leave_confirm,
            )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_main_menu,
        )
        player.send_form(form)

    def _get_guild_land_teleport_contrib_cost(self) -> int:
        raw = self.setting_manager.GetSetting("GUILD_LAND_TELEPORT_CONTRIB_COST")
        if raw is None or str(raw).strip() == "":
            return 10
        try:
            return max(0, int(str(raw).strip()))
        except (TypeError, ValueError):
            return 10

    def show_guild_lands_menu(self, player: Player):
        xuid = str(player.xuid)
        mem = self.guild_system.get_membership(xuid)
        if not mem:
            self.show_guild_main_menu(player)
            return
        gid = int(mem["guild_id"])
        cost = self._get_guild_land_teleport_contrib_cost()
        personal = self.guild_system.get_member_contribution(xuid)
        lands_map = self.land_system.get_guild_lands(gid)
        if cost > 0:
            hint = self._guild_text(
                "GUILD_LANDS_HINT_COST",
                "每次传送消耗 {0} 点个人公会贡献点（当前 {1}）。费用见配置 GUILD_LAND_TELEPORT_CONTRIB_COST。",
            ).format(int(cost), int(personal))
        else:
            hint = self._guild_text(
                "GUILD_LANDS_HINT_FREE",
                "当前配置为免费传送到公会领地。",
            )
        if lands_map:
            list_intro = hint
        else:
            list_intro = hint + "\n\n" + self._guild_text(
                "GUILD_LANDS_EMPTY", "当前公会还没有公会领地。"
            )
        form = ActionForm(
            title=self._guild_text("GUILD_LANDS_TITLE", "公会领地"),
            content=list_intro,
            on_close=None,
        )
        if not lands_map:
            form.add_button(
                self._guild_text("RETURN_BUTTON_TEXT", "返回"),
                on_click=self.show_guild_my_menu,
            )
            player.send_form(form)
            return
        for lid in sorted(lands_map.keys()):
            info = lands_map.get(lid) or {}
            lname = str(info.get("land_name") or f"#{lid}")
            dim = self.get_land_dimension(int(lid))
            btn = self._guild_text(
                "GUILD_LANDS_ROW",
                "{0}  #{1}  {2}",
            ).format(lname, int(lid), dim)

            def _open(p: Player, land_id: int = int(lid)):
                self.show_guild_land_teleport_confirm(p, land_id)

            form.add_button(btn, on_click=_open)
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_land_teleport_confirm(self, player: Player, land_id: int):
        xuid = str(player.xuid)
        mem = self.guild_system.get_membership(xuid)
        if not mem:
            self.show_guild_main_menu(player)
            return
        gid = int(mem["guild_id"])
        info = self.get_land_info(int(land_id))
        if not info:
            player.send_message(
                self._guild_text("GUILD_LAND_TP_INVALID", "[弧光核心]领地不存在。")
            )
            self.show_guild_lands_menu(player)
            return
        ogid = LandSystem.parse_land_owner_guild_id(info.get("owner_xuid"))
        if ogid is None or int(ogid) != gid:
            player.send_message(
                self._guild_text(
                    "GUILD_LAND_TP_NOT_GUILD_LAND",
                    "[弧光核心]该领地不属于本公会。",
                )
            )
            self.show_guild_lands_menu(player)
            return
        cost = self._get_guild_land_teleport_contrib_cost()
        personal = self.guild_system.get_member_contribution(xuid)
        lname = str(info.get("land_name") or "")
        dim = self.get_land_dimension(int(land_id))
        try:
            tpx, tpy, tpz = (
                int(info["tp_x"]),
                int(info["tp_y"]),
                int(info["tp_z"]),
            )
        except (KeyError, TypeError, ValueError):
            player.send_message(
                self._guild_text(
                    "GUILD_LAND_TP_NO_TP",
                    "[弧光核心]该领地未设置传送点。",
                )
            )
            self.show_guild_lands_menu(player)
            return
        if cost > 0:
            cost_block = self._guild_text(
                "GUILD_LAND_TP_CONFIRM_COST",
                "将消耗 {0} 点个人贡献点（当前 {1}）。",
            ).format(int(cost), int(personal))
        else:
            cost_block = self._guild_text(
                "GUILD_LAND_TP_CONFIRM_FREE", "本次传送不消耗贡献点。"
            )
        content = self._guild_text(
            "GUILD_LAND_TP_CONFIRM_CONTENT",
            "领地：{0}\n维度：{1}\n传送点：({2},{3},{4})\n\n{5}\n确定传送？",
        ).format(lname, dim, tpx, tpy, tpz, cost_block)
        form = ActionForm(
            title=self._guild_text("GUILD_LAND_TP_CONFIRM_TITLE", "传送到公会领地"),
            content=content,
            on_close=None,
        )

        def _yes(p: Player, lid: int = int(land_id)):
            self.teleport_to_guild_land_as_member(p, lid)

        form.add_button(
            self._guild_text("GUILD_CONFIRM_YES", "确定"),
            on_click=_yes,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "取消"),
            on_click=self.show_guild_lands_menu,
        )
        player.send_form(form)

    def teleport_to_guild_land_as_member(self, player: Player, land_id: int):
        xuid = str(player.xuid)
        mem = self.guild_system.get_membership(xuid)
        if not mem:
            self.show_guild_main_menu(player)
            return
        gid = int(mem["guild_id"])
        info = self.get_land_info(int(land_id))
        if not info:
            player.send_message(
                self._guild_text("GUILD_LAND_TP_INVALID", "[弧光核心]领地不存在。")
            )
            self.show_guild_lands_menu(player)
            return
        ogid = LandSystem.parse_land_owner_guild_id(info.get("owner_xuid"))
        if ogid is None or int(ogid) != gid:
            player.send_message(
                self._guild_text(
                    "GUILD_LAND_TP_NOT_GUILD_LAND",
                    "[弧光核心]该领地不属于本公会。",
                )
            )
            self.show_guild_lands_menu(player)
            return
        cost = self._get_guild_land_teleport_contrib_cost()
        if cost > 0:
            ok_c, err_c, new_p = self.guild_system.consume_member_contribution(
                xuid, cost
            )
            if not ok_c:
                if err_c == "GUILD_CONTRIB_NOT_ENOUGH":
                    cur = self.guild_system.get_member_contribution(xuid)
                    player.send_message(
                        self._guild_text(
                            "GUILD_LAND_TP_CONTRIB_NOT_ENOUGH",
                            "[弧光核心]个人贡献点不足（需要 {0}，当前 {1}）。",
                        ).format(int(cost), int(cur))
                    )
                else:
                    player.send_message(self._guild_err(err_c))
                self.show_guild_land_teleport_confirm(player, int(land_id))
                return
            player.send_message(
                self._guild_text(
                    "GUILD_LAND_TP_CONTRIB_DEDUCTED",
                    "[弧光核心]已消耗 {0} 点个人贡献点（剩余 {1}）。",
                ).format(int(cost), int(new_p))
            )
        tp_target_pos = self.get_land_teleport_point(int(land_id))
        self.run_player_task(
            player,
            lambda p, l_id=int(land_id), pos=tp_target_pos: self.delay_teleport_to_land(
                p, l_id, pos
            ),
            delay=45,
        )
        player.send_message(
            self.language_manager.GetText("READY_TELEPORT_TO_LAND").format(
                int(land_id)
            )
        )

    def show_guild_member_list_menu(self, player: Player, readonly: bool = True):
        mem = self.guild_system.get_membership(str(player.xuid))
        if not mem:
            self.show_guild_main_menu(player)
            return
        gid = int(mem["guild_id"])
        members = self.guild_system.list_members(gid)
        tier = self.guild_system.get_guild_size_tier(gid)
        cap = self.guild_system.get_size_tier_max(tier)
        header = self._guild_text(
            "GUILD_MEMBER_LIST_HEADER",
            "规模：{0}  人数：{1}/{2}",
        ).format(self._guild_size_tier_label(tier), len(members), cap)
        lines = [header]
        for m in members:
            xu = str(m.get("xuid") or "")
            rn = self.get_player_name_by_xuid(xu, return_with_title=False) or xu
            rl = self._guild_text(
                f"GUILD_ROLE_{str(m.get('role') or '').upper()}",
                str(m.get("role") or ""),
            )
            contrib = int(m.get("contribution") or 0)
            lines.append(
                self._guild_text(
                    "GUILD_MEMBER_LIST_ROW",
                    "{0}  [{1}]  贡献：{2}",
                ).format(rn, rl, contrib)
            )
        form = ActionForm(
            title=self._guild_text("GUILD_MEMBER_LIST_TITLE", "成员列表"),
            content="\n".join(lines)
            if members
            else self._guild_text("GUILD_MEMBER_LIST_EMPTY", "暂无成员"),
            on_close=None,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_invite_online_pick_menu(self, player: Player):
        """仅邀请当前在线、且未加入任何公会的玩家；点击后对方弹出确认，不入库邀请表。"""
        mem = self.guild_system.get_membership(str(player.xuid))
        if not mem or mem.get("role") not in (ROLE_OWNER, ROLE_MANAGER):
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(player)
            return
        gid = int(mem["guild_id"])
        try:
            online = list(getattr(self.server, "online_players", []) or [])
        except Exception:
            online = []
        candidates: List[Player] = []
        self_xuid = str(player.xuid)
        for op in online:
            try:
                if str(op.xuid) == self_xuid:
                    continue
                if self.guild_system.get_membership(str(op.xuid)):
                    continue
            except Exception:
                continue
            candidates.append(op)
        candidates.sort(key=lambda pl: (pl.name or "").lower())

        tier = self.guild_system.get_guild_size_tier(gid)
        cap = self.guild_system.get_size_tier_max(tier)
        cur = self.guild_system.count_members(gid)
        capacity_line = self._guild_text(
            "GUILD_INVITE_ONLINE_CAPACITY",
            "当前规模：{0}  人数：{1}/{2}",
        ).format(self._guild_size_tier_label(tier), cur, cap)
        base_content = self._guild_text(
            "GUILD_INVITE_ONLINE_CONTENT",
            "选择一名未加入公会的在线玩家，对方将收到确认窗口。",
        )
        form = ActionForm(
            title=self._guild_text("GUILD_INVITE_ONLINE_TITLE", "邀请在线玩家"),
            content=f"{capacity_line}\n{base_content}",
            on_close=None,
        )
        if cur >= cap:
            form.add_button(
                self._guild_text("GUILD_INVITE_ONLINE_FULL", "公会已满，无法继续邀请"),
                on_click=self.show_guild_my_menu,
            )
            form.add_button(
                self._guild_text("RETURN_BUTTON_TEXT", "返回"),
                on_click=self.show_guild_my_menu,
            )
            player.send_form(form)
            return
        if not candidates:
            form.add_button(
                self._guild_text(
                    "GUILD_INVITE_ONLINE_EMPTY",
                    "当前没有可邀请的在线玩家",
                ),
                on_click=self.show_guild_my_menu,
            )
        else:
            for tgt in candidates:
                label = tgt.name or "?"

                def _pick(inviter: Player, target: Player = tgt, g_id: int = gid):
                    self._guild_send_live_invite(inviter, target, g_id)

                form.add_button(label, on_click=_pick)
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_kick_menu(self, player: Player):
        actor_xuid = str(player.xuid)
        mem = self.guild_system.get_membership(actor_xuid)
        if not mem or mem.get("role") not in (ROLE_OWNER, ROLE_MANAGER):
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(player)
            return
        gid = int(mem["guild_id"])
        role = str(mem.get("role") or "")
        members = self.guild_system.list_members(gid)
        targets: List[Dict[str, Any]] = []
        for m in members:
            tx = str(m.get("xuid") or "")
            tr = str(m.get("role") or "")
            if tx == actor_xuid:
                continue
            if tr == ROLE_OWNER:
                continue
            if role == ROLE_MANAGER and tr != ROLE_MEMBER:
                continue
            targets.append(m)
        form = ActionForm(
            title=self._guild_text("GUILD_KICK_TITLE", "踢出成员"),
            content=self._guild_text("GUILD_KICK_CONTENT", "选择要移出公会的成员。"),
            on_close=None,
        )
        if not targets:
            form.add_button(
                self._guild_text("GUILD_KICK_NONE", "暂无可踢出的成员"),
                on_click=self.show_guild_my_menu,
            )
        for m in targets:
            tx = str(m.get("xuid") or "")
            disp = self.get_player_name_by_xuid(tx, return_with_title=False) or tx

            def _kick(p: Player, target: str = tx):
                ok, err = self.guild_system.kick(str(p.xuid), target)
                if ok:
                    p.send_message(
                        self._guild_text("GUILD_KICK_OK", "[弧光核心]已移出该成员。")
                    )
                    self._refresh_player_name_tag_by_xuid(target)
                else:
                    p.send_message(self._guild_err(err))
                self.show_guild_my_menu(p)

            form.add_button(disp, on_click=_kick)
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_set_role_pick_member(self, player: Player):
        actor_xuid = str(player.xuid)
        mem = self.guild_system.get_membership(actor_xuid)
        if not mem or mem.get("role") != ROLE_OWNER:
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(player)
            return
        gid = int(mem["guild_id"])
        members = self.guild_system.list_members(gid)
        form = ActionForm(
            title=self._guild_text("GUILD_SET_ROLE_PICK_TITLE", "变更职级"),
            content=self._guild_text(
                "GUILD_SET_ROLE_PICK_CONTENT", "选择一名成员（不含会长）。"
            ),
            on_close=None,
        )
        any_btn = False
        for m in members:
            tx = str(m.get("xuid") or "")
            if tx == actor_xuid:
                continue
            if str(m.get("role") or "") == ROLE_OWNER:
                continue
            any_btn = True
            disp = self.get_player_name_by_xuid(tx, return_with_title=False) or tx

            def _pick(p: Player, target: str = tx):
                self.show_guild_set_role_actions(p, target)

            form.add_button(disp, on_click=_pick)
        if not any_btn:
            form.add_button(
                self._guild_text("GUILD_SET_ROLE_NOBODY", "没有其他成员"),
                on_click=self.show_guild_my_menu,
            )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_set_role_actions(self, player: Player, target_xuid: str):
        form = ActionForm(
            title=self._guild_text("GUILD_SET_ROLE_ACTION_TITLE", "职级操作"),
            content=self._guild_text("GUILD_SET_ROLE_ACTION_CONTENT", "选择新职级。"),
            on_close=None,
        )

        def _set(p: Player, new_r: str):
            ok, err = self.guild_system.set_role(str(p.xuid), target_xuid, new_r)
            if ok:
                p.send_message(
                    self._guild_text("GUILD_SET_ROLE_OK", "[弧光核心]职级已更新。")
                )
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_my_menu(p)

        form.add_button(
            self._guild_text("GUILD_ROLE_PROMOTE_MANAGER", "设为管理者"),
            on_click=lambda p: _set(p, ROLE_MANAGER),
        )
        form.add_button(
            self._guild_text("GUILD_ROLE_DEMOTE_MEMBER", "设为普通成员"),
            on_click=lambda p: _set(p, ROLE_MEMBER),
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_set_role_pick_member,
        )
        player.send_form(form)

    def show_guild_leave_confirm(self, player: Player):
        form = ActionForm(
            title=self._guild_text("GUILD_LEAVE_TITLE", "退出公会"),
            content=self._guild_text(
                "GUILD_LEAVE_CONFIRM", "确定退出当前公会吗？"
            ),
            on_close=None,
        )

        def _yes(p: Player):
            ok, err = self.guild_system.leave(str(p.xuid))
            if ok:
                p.send_message(
                    self._guild_text("GUILD_LEAVE_OK", "[弧光核心]已退出公会。")
                )
                self._update_player_name_tag(p)
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_main_menu(p)

        form.add_button(
            self._guild_text("GUILD_CONFIRM_YES", "确定"),
            on_click=_yes,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "取消"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_disband_confirm(self, player: Player):
        form = ActionForm(
            title=self._guild_text("GUILD_DISBAND_TITLE", "解散公会"),
            content=self._guild_text(
                "GUILD_DISBAND_CONFIRM",
                "解散后所有成员将被移除，且不可恢复。确定吗？",
            ),
            on_close=None,
        )

        def _yes(p: Player):
            member_xuids: List[str] = []
            try:
                mem = self.guild_system.get_membership(str(p.xuid))
                if mem:
                    for row in self.guild_system.list_members(int(mem["guild_id"])):
                        xu = str(row.get("xuid") or "").strip()
                        if xu:
                            member_xuids.append(xu)
            except Exception:
                member_xuids = []
            ok, err = self.guild_system.disband(str(p.xuid))
            if ok:
                p.send_message(
                    self._guild_text("GUILD_DISBAND_OK", "[弧光核心]公会已解散。")
                )
                for xu in member_xuids:
                    self._refresh_player_name_tag_by_xuid(xu)
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_main_menu(p)

        form.add_button(
            self._guild_text("GUILD_CONFIRM_YES_DISBAND", "确定解散"),
            on_click=_yes,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "取消"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    # 公会改名（仅会长）
    def _refresh_guild_members_name_tag(self, guild_id: int) -> None:
        """改名/规模升级等场景：刷新该公会全体在线成员的展示名（含头顶名）。"""
        try:
            members = self.guild_system.list_members(int(guild_id))
        except Exception:
            members = []
        for m in members:
            xu = str(m.get("xuid") or "").strip()
            if xu:
                self._refresh_player_name_tag_by_xuid(xu)

    def show_guild_rename_panel(self, player: Player):
        xuid = str(player.xuid)
        mem = self.guild_system.get_membership(xuid)
        if not mem:
            self.show_guild_main_menu(player)
            return
        if str(mem.get("role") or "") != ROLE_OWNER:
            player.send_message(self._guild_err("GUILD_NOT_OWNER"))
            self.show_guild_my_menu(player)
            return
        gid = int(mem["guild_id"])
        g = self.guild_system.get_guild(gid)
        if not g:
            player.send_message(self._guild_err("GUILD_NOT_FOUND"))
            self.show_guild_my_menu(player)
            return
        old_name = guild_strip_mc_color_codes(g.get("name") or "").strip()
        cost = self.guild_system.get_rename_cost()
        cost_line = (
            self._guild_text(
                "GUILD_RENAME_COST_LABEL",
                "改名费用：{0}（将立即扣除）",
            ).format(self._format_money_display(cost))
            if cost > 0
            else self._guild_text("GUILD_RENAME_FREE_LABEL", "改名免费。")
        )
        info = Label(
            text=self._guild_text(
                "GUILD_RENAME_INFO",
                "当前公会名：{0}\n{1}",
            ).format(old_name, cost_line)
        )
        new_name_in = TextInput(
            label=self._guild_text(
                "GUILD_RENAME_INPUT_LABEL",
                "新公会名称（最多8字；禁止 [ ] \" 与 § 颜色/样式符号）",
            ),
            placeholder=self._guild_text(
                "GUILD_RENAME_INPUT_PLACEHOLDER", "请输入新公会名"
            ),
            default_value=old_name,
        )

        def _submit(p: Player, json_str: str):
            try:
                data = json.loads(json_str)
            except Exception:
                p.send_message(
                    self._guild_text("GUILD_CREATE_INVALID", "[弧光核心]输入无效。")
                )
                self.show_guild_rename_panel(p)
                return
            if len(data) < 2:
                self.show_guild_rename_panel(p)
                return
            new_name = str(data[1])
            ok, err, ri = self.guild_system.rename_guild(str(p.xuid), new_name)
            if ok:
                paid = float(ri.get("cost") or 0.0)
                if paid > 0:
                    p.send_message(
                        self._guild_text(
                            "GUILD_RENAME_OK_PAID",
                            "[弧光核心]公会已改名为 {0}（消耗 {1}）。",
                        ).format(
                            ri.get("new_name") or new_name,
                            self._format_money_display(paid),
                        )
                    )
                else:
                    p.send_message(
                        self._guild_text(
                            "GUILD_RENAME_OK",
                            "[弧光核心]公会已改名为 {0}。",
                        ).format(ri.get("new_name") or new_name)
                    )
                self._refresh_guild_members_name_tag(int(ri.get("guild_id") or 0))
                self.show_guild_my_menu(p)
            else:
                p.send_message(self._guild_err(err))
                if err in (
                    "GUILD_NAME_TAKEN",
                    "GUILD_INVALID_NAME",
                    "GUILD_NAME_TOO_LONG",
                    "GUILD_NAME_FORBIDDEN_CHARS",
                    "GUILD_NAME_NO_COLOR_CODES",
                    "GUILD_RENAME_SAME_NAME",
                ):
                    self.show_guild_rename_panel(p)
                else:
                    self.show_guild_my_menu(p)

        form = ModalForm(
            title=self._guild_text("GUILD_RENAME_TITLE", "公会改名"),
            controls=[info, new_name_in],
            on_close=None,
            on_submit=_submit,
        )
        player.send_form(form)

    # 升级公会规模（消耗公共贡献点）
    def show_guild_upgrade_tier_menu(self, player: Player):
        xuid = str(player.xuid)
        mem = self.guild_system.get_membership(xuid)
        if not mem:
            self.show_guild_main_menu(player)
            return
        role = str(mem.get("role") or "")
        if role not in (ROLE_OWNER, ROLE_MANAGER):
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(player)
            return
        gid = int(mem["guild_id"])
        cur_tier = self.guild_system.get_guild_size_tier(gid)
        cur_cap = self.guild_system.get_size_tier_max(cur_tier)
        cur_count = self.guild_system.count_members(gid)
        guild_contrib = self.guild_system.get_guild_total_contribution(gid)

        candidate_tiers = [
            t
            for t in (SIZE_TIER_MEDIUM, SIZE_TIER_LARGE)
            if self.guild_system._tier_rank(t)
            > self.guild_system._tier_rank(cur_tier)
        ]
        content = self._guild_text(
            "GUILD_UPGRADE_TIER_CONTENT",
            "当前规模：{0}（人数 {1}/{2}）\n公会贡献点：{3}\n选择目标规模（消耗公会公共贡献点）：",
        ).format(self._guild_size_tier_label(cur_tier), cur_count, cur_cap, int(guild_contrib))
        form = ActionForm(
            title=self._guild_text("GUILD_UPGRADE_TIER_TITLE", "升级公会规模"),
            content=content,
            on_close=None,
        )

        if not candidate_tiers:
            form.add_button(
                self._guild_text("GUILD_UPGRADE_TIER_AT_MAX", "已是最高规模"),
                on_click=self.show_guild_my_menu,
            )
        else:
            for t in candidate_tiers:
                cap = self.guild_system.get_size_tier_max(t)
                cost = self.guild_system.get_upgrade_cost(t)
                affordable = guild_contrib >= cost
                label_key = (
                    "GUILD_UPGRADE_TIER_BTN_OK"
                    if affordable
                    else "GUILD_UPGRADE_TIER_BTN_LACK"
                )
                default_template = (
                    "{0}（≤{1} 人，需 {2} 贡献点）"
                    if affordable
                    else "{0}（≤{1} 人，需 {2} 贡献点，不足）"
                )
                label = self._guild_text(label_key, default_template).format(
                    self._guild_size_tier_label(t), cap, int(cost)
                )

                def _open(p: Player, target_tier: str = t):
                    self.show_guild_upgrade_tier_confirm(p, target_tier)

                form.add_button(label, on_click=_open)
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_guild_my_menu,
        )
        player.send_form(form)

    def show_guild_upgrade_tier_confirm(self, player: Player, target_tier: str):
        xuid = str(player.xuid)
        mem = self.guild_system.get_membership(xuid)
        if not mem:
            self.show_guild_main_menu(player)
            return
        role = str(mem.get("role") or "")
        if role not in (ROLE_OWNER, ROLE_MANAGER):
            player.send_message(self._guild_err("GUILD_NO_PERMISSION"))
            self.show_guild_my_menu(player)
            return
        target = self.guild_system.normalize_size_tier(target_tier)
        if target not in (SIZE_TIER_MEDIUM, SIZE_TIER_LARGE):
            self.show_guild_upgrade_tier_menu(player)
            return
        gid = int(mem["guild_id"])
        cur_tier = self.guild_system.get_guild_size_tier(gid)
        if self.guild_system._tier_rank(target) <= self.guild_system._tier_rank(cur_tier):
            player.send_message(self._guild_err("GUILD_TIER_NOT_UPGRADABLE"))
            self.show_guild_upgrade_tier_menu(player)
            return
        cap = self.guild_system.get_size_tier_max(target)
        cost = self.guild_system.get_upgrade_cost(target)
        guild_contrib = self.guild_system.get_guild_total_contribution(gid)
        confirm_content = self._guild_text(
            "GUILD_UPGRADE_TIER_CONFIRM",
            "将公会规模升级为：{0}（≤{1} 人）\n消耗公会公共贡献点：{2}\n升级后剩余：{3}\n（操作不可撤销）",
        ).format(
            self._guild_size_tier_label(target),
            cap,
            int(cost),
            int(max(0, guild_contrib - cost)),
        )
        form = ActionForm(
            title=self._guild_text("GUILD_UPGRADE_TIER_CONFIRM_TITLE", "确认升级"),
            content=confirm_content,
            on_close=None,
        )

        def _yes(p: Player, _target: str = target):
            actor_xuid = str(p.xuid)
            ok, err, info = self.guild_system.upgrade_size_tier_with_contribution(
                actor_xuid, _target
            )
            if ok:
                p.send_message(
                    self._guild_text(
                        "GUILD_UPGRADE_TIER_OK",
                        "[弧光核心]公会规模已升级为 {0}（消耗 {1} 贡献点，剩余 {2}）。",
                    ).format(
                        self._guild_size_tier_label(info.get("new_tier") or _target),
                        int(info.get("cost") or 0),
                        int(info.get("guild_total_contribution") or 0),
                    )
                )
                self._refresh_guild_members_name_tag(int(info.get("guild_id") or 0))
            else:
                p.send_message(self._guild_err(err))
            self.show_guild_my_menu(p)

        form.add_button(
            self._guild_text("GUILD_CONFIRM_YES", "确定"),
            on_click=_yes,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "取消"),
            on_click=self.show_guild_upgrade_tier_menu,
        )
        player.send_form(form)

    # OP - 公会管理
    def show_op_guild_manage_panel(self, player: Player):
        if not player.is_op:
            player.send_message(self.language_manager.GetText("OP_PANEL_NO_PERMISSION"))
            return
        guilds = self.guild_system.list_guilds_directory("")
        small_max = self.guild_system.get_size_tier_max(SIZE_TIER_SMALL)
        medium_max = self.guild_system.get_size_tier_max(SIZE_TIER_MEDIUM)
        large_max = self.guild_system.get_size_tier_max(SIZE_TIER_LARGE)
        header = self._guild_text(
            "OP_GUILD_MANAGE_HEADER",
            "公会规模门槛：小型≤{0} / 中型≤{1} / 大型≤{2}（在 core_setting.yml 修改）",
        ).format(small_max, medium_max, large_max)
        if not guilds:
            header += "\n" + self._guild_text("OP_GUILD_MANAGE_EMPTY", "目前没有公会。")
        form = ActionForm(
            title=self._guild_text("OP_GUILD_MANAGE_TITLE", "公会管理"),
            content=header,
            on_close=None,
        )
        for g in guilds:
            try:
                gid = int(g.get("id") or 0)
            except (TypeError, ValueError):
                continue
            if gid <= 0:
                continue
            gname = guild_strip_mc_color_codes(g.get("name")).strip()
            tier = self.guild_system.normalize_size_tier(g.get("size_tier"))
            cap = self.guild_system.get_size_tier_max(tier)
            cur = self.guild_system.count_members(gid)
            label = self._guild_text(
                "OP_GUILD_MANAGE_ROW",
                "{0}  规模：{1}  人数：{2}/{3}  贡献点：{4}",
            ).format(
                gname,
                self._guild_size_tier_label(tier),
                cur,
                cap,
                int(g.get("total_contribution") or 0),
            )

            def _open(p: Player, _gid: int = gid):
                self.show_op_guild_detail_panel(p, _gid)

            form.add_button(label, on_click=_open)
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_op_main_panel,
        )
        player.send_form(form)

    def show_op_guild_detail_panel(self, player: Player, guild_id: int):
        if not player.is_op:
            player.send_message(self.language_manager.GetText("OP_PANEL_NO_PERMISSION"))
            return
        g = self.guild_system.get_guild(int(guild_id))
        if not g:
            player.send_message(self._guild_err("GUILD_NOT_FOUND"))
            self.show_op_guild_manage_panel(player)
            return
        gid = int(g.get("id") or guild_id)
        gname = str(g.get("name") or "")
        tier = self.guild_system.normalize_size_tier(g.get("size_tier"))
        cap = self.guild_system.get_size_tier_max(tier)
        cur = self.guild_system.count_members(gid)
        owner_xuid = str(g.get("owner_xuid") or "")
        owner_name = self.get_player_name_by_xuid(owner_xuid, return_with_title=False) or owner_xuid
        info_lines = [
            self._guild_text("OP_GUILD_DETAIL_NAME", "公会：{0}").format(gname),
            self._guild_text("OP_GUILD_DETAIL_OWNER", "会长：{0}").format(owner_name),
            self._guild_text(
                "OP_GUILD_DETAIL_SIZE",
                "规模：{0}  人数：{1}/{2}",
            ).format(self._guild_size_tier_label(tier), cur, cap),
            self._guild_text(
                "OP_GUILD_DETAIL_CONTRIB",
                "公共贡献点：{0}",
            ).format(int(g.get("total_contribution") or 0)),
        ]
        form = ActionForm(
            title=self._guild_text("OP_GUILD_DETAIL_TITLE", "公会详情"),
            content="\n".join(info_lines),
            on_close=None,
        )

        def _change_tier(p: Player, _gid: int = gid):
            self.show_op_guild_change_tier_panel(p, _gid)

        form.add_button(
            self._guild_text("OP_GUILD_BTN_CHANGE_TIER", "调整公会规模"),
            on_click=_change_tier,
        )
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=self.show_op_guild_manage_panel,
        )
        player.send_form(form)

    def show_op_guild_change_tier_panel(self, player: Player, guild_id: int):
        if not player.is_op:
            player.send_message(self.language_manager.GetText("OP_PANEL_NO_PERMISSION"))
            return
        g = self.guild_system.get_guild(int(guild_id))
        if not g:
            player.send_message(self._guild_err("GUILD_NOT_FOUND"))
            self.show_op_guild_manage_panel(player)
            return
        gid = int(g.get("id") or guild_id)
        cur_tier = self.guild_system.normalize_size_tier(g.get("size_tier"))
        cur_cap = self.guild_system.get_size_tier_max(cur_tier)
        cur_count = self.guild_system.count_members(gid)
        form = ActionForm(
            title=self._guild_text("OP_GUILD_TIER_TITLE", "调整公会规模"),
            content=self._guild_text(
                "OP_GUILD_TIER_CONTENT",
                "公会：{0}\n当前规模：{1}（人数 {2}/{3}）",
            ).format(g.get("name", ""), self._guild_size_tier_label(cur_tier), cur_count, cur_cap),
            on_close=None,
        )

        def _set_tier(p: Player, target_tier: str, _gid: int = gid):
            cap2 = self.guild_system.get_size_tier_max(target_tier)
            count2 = self.guild_system.count_members(_gid)
            if count2 > cap2:
                p.send_message(
                    self._guild_text(
                        "OP_GUILD_TIER_DOWNGRADE_BLOCK",
                        "[弧光核心]当前人数 {0} 超过目标规模上限 {1}，请先减少成员后再降级。",
                    ).format(count2, cap2)
                )
                self.show_op_guild_detail_panel(p, _gid)
                return
            ok, err = self.guild_system.set_size_tier(_gid, target_tier)
            if ok:
                p.send_message(
                    self._guild_text(
                        "OP_GUILD_TIER_OK",
                        "[弧光核心]已将公会规模设为 {0}（上限 {1}）。",
                    ).format(self._guild_size_tier_label(target_tier), cap2)
                )
                self._refresh_guild_members_name_tag(_gid)
            else:
                p.send_message(self._guild_err(err))
            self.show_op_guild_detail_panel(p, _gid)

        for tier in SIZE_TIERS:
            cap = self.guild_system.get_size_tier_max(tier)
            label = self._guild_text(
                "OP_GUILD_TIER_BTN",
                "{0}（≤{1} 人）",
            ).format(self._guild_size_tier_label(tier), cap)
            if tier == cur_tier:
                label = "✓ " + label
            form.add_button(label, on_click=lambda p, t=tier: _set_tier(p, t))
        form.add_button(
            self._guild_text("RETURN_BUTTON_TEXT", "返回"),
            on_click=lambda p, _gid=gid: self.show_op_guild_detail_panel(p, _gid),
        )
        player.send_form(form)

    # Bank
