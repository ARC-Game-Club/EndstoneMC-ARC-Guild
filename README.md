# EndstoneMC-ARC-Guild / 弧光公会

[![Version](https://img.shields.io/badge/version-v0.1.2-blue)](https://github.com/ARC-Minecraft/EndstoneMC-ARC-Guild)
[![Python](https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![EndStone API](https://img.shields.io/badge/EndStone_API-0.10-black)](https://github.com/EndstoneMC/endstone)

弧光公会插件（从 `arc_core` 完整拆出）。**依赖同服已安装的 arc_core ≥ v0.9.50**（经济、主菜单注册、聊天前缀、跨服同步 API）。

- **版本**: 0.1.2
- **插件 id**: `arc_guild`
- **数据目录**: `plugins/ARCGuild/`（`guild.db`、`guild_setting.yml`、`ZH-CN.txt`）
- **命令**: `/arcguild`、`/arcguildop`（OP）
- **跨服**: 经 `arc_core.api_sync_*` 同步 `guilds` / `guild_members` / `guild_invites` / `guild_join_requests`

## 功能

- 创建 / 解散 / 改名 / 规模升级（小 / 中 / 大）
- 邀请、申请入会、审核、踢出、职级（会长 / 管理 / 成员）
- 个人与公会公共贡献点
- 浏览全部公会、入会策略
- 主菜单入口自行注册（`arc_guild:menu`）
- 领地：核心圈地面板在检测到本插件且玩家为会长/管理者时出现「创建公会领地」

## 安装

1. 安装并配置好 **arc_core**（≥ 0.9.50，从服开启 `ENABLE_SYNC_CLIENT`）
2. 将本插件 wheel 装入服务器环境并重启
3. 首次启动会尝试从 `plugins/ARCCore` 主库迁移公会四表到 `plugins/ARCGuild/guild.db`，成功后写 `migrated.flag`

## 构建

```bash
pip install build && python -m build
# 输出 dist/endstone_arc_guild-0.1.0-py2.py3-none-any.whl
```

## 与核心的边界

| 方向 | 说明 |
|---|---|
| 本插件 → 核心 | 经济扣费/退款、主菜单、聊天前缀、跨服同步、领地列表/传送 |
| 核心 → 本插件 | 软依赖：`api_get_player_guild_id`、`api_is_same_guild`、贡献、公会领地资格等；**查询失败一律视为无公会（领地不放行）** |

## 更新日志

### v0.1.2（当前版本）

- ✅ **修复加载失败**：`guild_menus` 补齐 `Callable`/`json`/表单组件等导入；`GUILD_BROWSE_PAGE_SIZE` 与公会领地 owner 解析改为插件内实现

### v0.1.1

- ✅ 公会名经核心注册制前缀提交：槽名 `guild`、priority=2；入会/改名/升降级/跨服下行后自动刷新
- ✅ 无公会时清除前缀显示（不再固定显示 `[无公会]`）

### v0.1.0

- ✅ 首个独立版本：公会领域逻辑、玩家/OP UI、命令、自有 SQLite 与跨服同步接线
- ✅ 启动时从弧光核心主库自动迁移公会表
- ✅ 主菜单入口由本插件注册
