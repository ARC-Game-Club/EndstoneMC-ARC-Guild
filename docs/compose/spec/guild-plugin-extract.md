---
feature: guild-plugin-extract
status: in-progress
updated: 2026-02-14
branch: master
commits: 
---

# 公会插件完整拆出

## Report

## [S1] Problem

公会逻辑、UI、命令、API 全部焊在弧光核心（`arc_core`）里：`GuildSystem.py` + `arc_core_plugin.py` 中约 58 个公会相关方法、约 2000 行表单 UI，并与领地（GUILD_ 主人键）、击杀贡献、签到贡献、聊天前缀深度纠缠。无法独立发版，也无法把公会表纳入「插件自有库 + 通用跨服同步」模型。

## [S2] Design

### 目标

- 新仓 `EndstoneMC-ARC-Guild`（包 `endstone_arc_guild`，插件 id `arc_guild`，数据目录 `plugins/ARCGuild/`）。
- 公会领域逻辑 + 全部玩家/OP UI + 命令迁入新插件。
- 跨服：经 `arc_core` 的 `api_sync_*` 同步 `guilds` / `guild_members` / `guild_invites` / `guild_join_requests`。
- 核心：**删除**全部 `guild_system`、`show_guild_*`、`api_*guild*`、内置 guild 同步类别与主菜单公会入口；领地公会判定改为对 `arc_guild` 的软依赖。
- 首次启动自动从 `plugins/ARCCore` 主库迁移四张表到 `plugins/ARCGuild/guild.db`。

### 依赖边界（新插件 → 核心）

| 能力 | 方式 |
|---|---|
| 经济扣费/退费/查询 | `api_get_player_money` / `api_adjust_player_money` / `api_change_player_money` |
| 主菜单入口 | 公会插件自行 `api_register_main_menu_button("arc_guild:menu", ...)`（核心不再内置） |
| 聊天前缀 | `api_register_chat_prefix("guild", 2)` + `api_set_player_chat_prefix` |
| 领地列表/传送 | `api_get_guild_lands`、`api_teleport_player_to` 等 |
| 圈地建公会领地 | 核心待购面板调用 `api_get_guild_land_eligibility` / `api_consume_guild_contribution_for_land` / `api_refund_guild_contribution_pool`；未装插件则不出现「创建公会领地」按钮 |
| 跨服同步 | `api_sync_register_namespace` / `api_sync_upsert` / `api_sync_delete` |
| 玩家名解析 | `api_get_player_xuid_by_name` / `api_get_player_name_by_xuid` |

核心缺失时：经济/领地相关操作失败并提示；同步 no-op；菜单仍可注册失败则仅用 `/arcguild` 命令。

**公会领地权限（失败即拒绝）**：核心判定 `GUILD_` 领地时，若 `arc_guild` 未安装、查询抛错、或拿不到 membership，一律视为与该领地无关（无权限），绝不放行。

### 核心软依赖（核心 → 公会插件）

`server.get_plugin('arc_guild')` 存在时调用：

- `api_get_player_guild_id(xuid=...)`
- `api_get_guild_info(guild_id)`
- `api_is_same_guild(xuid_a, xuid_b)`
- `api_add_guild_contribution(xuid=..., points=...)`
- `api_set_guild_chat_prefix(xuid)`（或由公会插件主动 set prefix）

任一调用失败或返回空 → 按无公会处理（领地不放行、无贡献、前缀无公会）。

### 数据模型（`plugins/ARCGuild/guild.db`）

沿用现有四表结构（见 `GuildSystem.ensure_tables`）。主键：

- `guilds`: `id`
- `guild_members`: `(guild_id, xuid)`
- `guild_invites`: `id`
- `guild_join_requests`: `id`

同步命名空间 `arc_guild`，逻辑表名 `arc_guild:guilds` 等。本地写成功后 `api_sync_upsert`/`api_sync_delete`；下行 `on_apply` 写本地库（suppress 回环由插件侧标志位处理，不用核心 DB notify）。

### 迁移

启动时若 `plugins/ARCGuild/migrated.flag` 不存在且核心库存在 guilds 表有数据：

1. ATTACH/打开核心 `DATABASE_PATH`（默认 `plugins/ARCCore/arc.db`，以核心 Setting 为准，缺省常见路径探测）
2. `INSERT OR IGNORE` 拷贝四表
3. 写 `migrated.flag`

失败不阻断启动，打错误日志。

### 命令与菜单

- `/arcguild` — 打开公会主菜单（权限默认所有人）
- 主菜单按钮：向核心注册，priority=3（与其它核心功能同层）
- OP：`/arcguildop` — 公会管理面板

### 配置（`plugins/ARCGuild/guild_setting.yml`）

沿用 KEY=VALUE。键：`GUILD_CREATE_COST`、`GUILD_RENAME_COST`、`GUILD_SIZE_*`、`GUILD_UPGRADE_*`、`GUILD_LAND_TP_CONTRIB_COST` 等。不再走核心 `SYNC_CATEGORY_SHARED_SETTINGS` 的 guild 白名单（核心删除该类）。

## [S3] Out of Scope

- 核心领地系统重构（仅软依赖查询）
- 公会战/公会等级经验树等新玩法
- 旧核心同步枚举值从协议中物理删除（保留枚举以免旧包解码炸）
- 多语言除 ZH-CN 外的翻译

## Tasks

- [ ] T1: 新仓脚手架与 GuildSystem/经济桥/自有库 — acceptance: 包可 import（无 endstone 时测领域逻辑），ensure_tables + CRUD 单测通过 (covers: S2)
- [ ] T2: 迁移与跨服同步接线 — acceptance: 迁移逻辑单测（临时 SQLite）；register_namespace 后本地写调用 api_sync_*（mock） (covers: S2; depends: T1)
- [ ] T3: 玩家/OP UI 与命令 — acceptance: 菜单方法齐全，`/arcguild` 注册，语言键迁入 ZH-CN.txt (covers: S2; depends: T1)
- [ ] T4: 核心剥离与软依赖 — acceptance: 核心无 guild_system/show_guild/api_*guild*；领地/击杀/签到/前缀走 get_plugin('arc_guild')；SYNC_CLIENT_SYNC_GUILD 移除 (covers: S2; depends: T1-T3)
- [ ] T5: 验证与评审 — acceptance: 双仓 unittest 通过；py_compile 通过 (covers: S2; depends: T1-T4)
