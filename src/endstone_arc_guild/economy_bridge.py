# -*- coding: utf-8 -*-
"""经济桥：把 arc_core 的 api_* 适配成 GuildSystem 期望的 economy 接口。"""
from __future__ import annotations

from typing import Optional


class EconomyBridge:
    """GuildSystem 依赖：round_money / 余额判断 / 扣款 / 退款。"""

    def __init__(self, arc_core=None):
        self._arc = arc_core

    def set_core(self, arc_core) -> None:
        self._arc = arc_core

    def _core(self):
        return self._arc

    @staticmethod
    def round_money(value: float) -> float:
        return round(float(value or 0), 2)

    def format_money_display(self, value: float) -> str:
        return "%.2f" % self.round_money(value)

    def get_player_money_by_xuid(self, xuid: str) -> float:
        core = self._core()
        if core is None:
            return 0.0
        try:
            return float(core.api_get_player_money(xuid=str(xuid or "")))
        except Exception:
            return 0.0

    def judge_if_player_has_enough_money_by_xuid(self, xuid: str, amount: float) -> bool:
        return self.get_player_money_by_xuid(xuid) + 1e-9 >= self.round_money(amount)

    def decrease_player_money_by_xuid(self, xuid: str, amount: float) -> bool:
        core = self._core()
        if core is None:
            return False
        amt = self.round_money(amount)
        if amt <= 0:
            return True
        try:
            r = core.api_adjust_player_money(xuid=str(xuid or ""), delta=-amt)
            if isinstance(r, dict):
                return bool(r.get("success"))
            return bool(r)
        except Exception:
            return False

    def increase_player_money_by_xuid(self, xuid: str, amount: float) -> bool:
        core = self._core()
        if core is None:
            return False
        amt = self.round_money(amount)
        if amt <= 0:
            return True
        try:
            r = core.api_adjust_player_money(xuid=str(xuid or ""), delta=amt)
            if isinstance(r, dict):
                return bool(r.get("success"))
            return bool(r)
        except Exception:
            return False
