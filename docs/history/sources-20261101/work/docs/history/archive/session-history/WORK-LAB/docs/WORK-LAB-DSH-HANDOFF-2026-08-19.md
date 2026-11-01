# WORK-LAB → DeepSeek Harness 交接摘要（2026-08-19）

> 增量覆盖 2026-08-18 版（迁移 + 桌面版修复）：本轮 = **更新机制落地 + 颜色彻底修复 + 自动维护系统 + 插件治理 + 前端增强**。DSH 接手工作时，以本文件 + 08-18 交接 + AGENTS.md + 50-taskpacks 为唯一权威。
>
> 交接人：Hermes（WORK-LAB 唯一 Writer）· 接手方：DeepSeek Harness（受限 Agent Runtime）

---

## 0. TL;DR

- **自动维护系统上线**：`D:\All projects\DSH\dsh-maintain.js` + dsh-desktop 启动钩子（`main.rs ensure_dsh_maintenance`，exe 已重建）——**打开桌面 DSH 自动执行**：颜色补丁重打 → obsidian-memory 崩溃修复 → 原生二进制检查修复 → 插件增量更新 → 更新后颜色补丁再重打 → 自动重启 web → 健康验证。全部幂等，日志 `dsh-maintain.log`，失败不阻塞启动。
- **颜色问题彻底根治**（三层）：① 根因 = dsh-update-checker 按钮用 `brand-primary`（品牌强调色，深色/皮肤下可能近白/浅蓝）做背景 + 硬编码 `color:#fff`；② 修复 = 补丁升级为官方语义变量 `--dsw-alias-button-primary-fill`（按钮填充色）+ `--dsw-alias-label-primary-foreground`（对比文字色）——**任何皮肤下都可读**（鲸吟下实测深蓝底白字）；③ maintain 启动自动重打（防 pnpm 还原/插件更新覆盖）。
- **插件治理**：30 个插件全部最新（updatable: 0，除 remote-web-ui 跳过）；新增 `dsh-codex-meter`（DeepSeek 用量仪表板 v1.2.2 已生效）；`dsh-client-ui-obsidian-memory` 0.3.2 已装（config 崩溃已修，**vault 路径由用户自填**——侧边栏 Obsidian Memory 面板选目录 / cordis.patch.yml 配 vaultPath / 环境变量 OBSIDIAN_VAULT_PATH）；dsh-skins/describe-image 确认冗余但属聚合依赖无法独立卸载（无负载保留）；**市场调研**：1520 插件（awesome-dsh-plugin 注册表，20 分类），自研融合判定 = 不需要（社区全覆盖）。
- **前端**：鲸吟皮肤（whale-song）已应用生效（深蓝 `#081a40` 底 + 浅蓝字）；wallpaper-engine-dsh 未装（本机无 Wallpaper Engine）；workbench 未装（0.0.5 早期版风险）。
- **踩雷记录（全部处置，SOP 已更新）**：① pnpm 还原陷阱（market 装插件触发 pnpm install → 从 lockfile 还原插件到旧版本 + 覆盖文件补丁）→ 根治 = package.json 依赖声明同步最新（update-dsh-plugins.py 内置）；② web-search-pro 坏插件（引用 @anweat/dsh-browser 未声明 → boot 崩）→ 已回滚移除；③ remote-web-ui 更新卡 cloudflared 下载（网络）→ 跳过（0.2.0 可用）；④ obsidian-memory config=undefined 崩溃（cordis rc.5 传 config undefined，插件读 config.vaultPath）→ 一行修复（`config = {}`）+ maintain 兜底；⑤ lightningcss 二进制缺失（可选依赖未装）→ 手动下载放置（SOP §5.1）。
- **当前运行态**：web PID 1976（127.0.0.1:3080 HTTP 200，日志 `.hermes/task-runtime/dsh-dest-web.log`）；dsh-desktop 运行中（鲸鱼图标）；31 插件；鲸吟皮肤；颜色全对。

---

## 1. 自动维护系统（本轮核心交付）

### 1.1 组成

| 件 | 位置 | 作用 |
|---|---|---|
| `dsh-maintain.js` | `D:\All projects\DSH\` | 幂等维护脚本：`--fix`（默认，全自动修复）/ `--check`（只查）|
| `main.rs` 钩子 | `dsh-desktop/src-tauri/src/main.rs` | `ensure_dsh_maintenance()`——`ensure_dsh_service()` 后 spawn `node dsh-maintain.js --fix`（detached，不阻塞）|
| exe | `dsh-desktop/src-tauri/target/release/dsh-desktop.exe` | 已重建（8.5s 增量），含维护钩子；setup 同步更新 |

### 1.2 自动项（--fix 顺序）

1. `fixColorPatch(apply)`：颜色补丁——背景 `brand-primary → button-primary-fill` + 文字 `#fff → label-primary-foreground`（幂等，两段独立检查）
2. `obsidianMemoryFix(apply)`：obsidian-memory `config = {}` 崩溃修复（防更新/重装覆盖）
3. `fixNativeBinaries(apply)`：lightningcss 类原生二进制缺失 → npm registry 下载放置
4. `updatePlugins(apply)`：有可更新插件 → 官方 API 批量更新（备份回滚）→ 返回 RESTART
5. 更新后重打颜色补丁 → `restartWeb()` → `webHealthy()`

### 1.3 验证（2026-08-19 实测）

```
[14:05:38] == dsh-maintain --fix ==
[14:05:38] color-patch: OK (already applied)
[14:05:38] obsidian-memory: config fix OK
[14:05:38] native-bin: OK
[14:05:40] plugins: updating 3 ... OK installed=0.1.28 / 0.13.1 / 0.3.7
[14:06:46] color-patch: OK
[14:06:56] web: restarting → healthy
[14:06:56] == done (OK) ==   (exit 0)
```

---

## 2. 颜色问题彻底修复（完整证据链）

### 2.1 根因（两层）

1. **插件用错变量**：`.dsh-update-btn-primary` / `.dsh-plugin-btn-primary` 用 `background:var(--dsw-alias-brand-primary)`（**品牌强调色**——官方深色下 = 近白 #f9fafb，鲸吟皮肤下 = 浅蓝 #8ab4de）做按钮背景 + 硬编码 `color:#fff` → 白底白字/浅蓝底白字。
2. **官方语义**：按钮填充 = `--dsw-alias-button-primary-fill`（官方深色 = brand-primary；鲸吟皮肤 = 深蓝 #2f6fb8）；对比文字 = `--dsw-alias-label-primary-foreground`（官方深色 = 深 #0f1115；鲸吟 = 白 #fff）。

### 2.2 修复（补丁内容，maintain 自动重打）

```css
.dsh-update-btn-primary {
  background: var(--dsw-alias-button-primary-fill, #4f8cff);  /* 原 brand-primary */
  border-color: var(--dsw-alias-brand-primary, #4f8cff);
  color: var(--dsw-alias-label-primary-foreground, #0f1115);  /* 原 #fff */
}
/* .dsh-plugin-btn-primary 同 */
```

### 2.3 实测验证（浏览器 computed）

- 鲸吟皮肤下：`background: rgb(47,111,184)`（深蓝）+ `color: rgb(255,255,255)`（白）——高对比 ✓
- 官方深色下：button-primary-fill（近白底）+ label-primary-foreground（深字）——✓

### 2.4 持久化（三层防御）

1. package.json 声明同步（`^1.4.8`）防 pnpm 版本还原
2. maintain 启动自动重打（防任何覆盖）
3. 官方语义变量（任何皮肤/主题下天然正确）

---

## 3. 插件治理结果

### 3.1 最终清单（31 个）

- **市场管理 14**：auto-memory、vision-toolkit、web-ui-all、modlens、computer-use、effort-slider、find-plugin、mermaid、monitor、tier-router、update-checker(1.4.8)、vision-tools、voice-input-web、dshmarket(1.15.0)
- **web-ui-all 聚合（linxin666 系列）**：aionui-panel、community-plugins、git-graph、plugin-manager、skill-explorer、skin-center、task-board、web-ui-settings、liangshen、pet、remote-web-ui、skins、ssh、describe-image
- **独立/其他**：better-sidebar(0.13.1)、codex-meter(1.2.2 新增)、obsidian-memory(0.3.2 新增，手动放置 github 源)、update-checker、monitor 等
- **跳过更新**：remote-web-ui（cloudflared 下载网络不通，0.2.0 功能可用）

### 3.2 去重结论

- **dsh-skins**：已退役（皮肤并入 skin-center），纯依赖残留无负载 → 保留（等官方清理周期）
- **describe-image**：与 vision-tools 的 vision_understand 重叠，但属 web-ui-all 聚合依赖 → 无法独立卸载 → 保留（无实际负担）
- **面板重叠**：better-sidebar（VSCode 风格）vs aionui-panel（AionUi）→ 用户选"都要"→ 都留
- **自研融合**：市场 1520 插件已覆盖全部需求域 → 判定不需要

### 3.3 市场调研结论（可选后续）

- 余额/用量：`dsh-codex-meter`（已装）/ `dsh-usage-dashboard-plus` / `dsh-token-billing`
- 搜索：`dsh-web-search-pro`（**坏插件已回滚**）/ `dsh-free-search`（免费 7 引擎）
- 视觉增强：`dsh-vision-fallback`（观察/推理分离，比 vision-tools 智能）
- 记忆替代：`dsh-client-ui-obsidian-memory`（已装）
- 前端：`dsh-plugin-workbench`（0.0.5 早期未装）、`wallpaper-engine-dsh`（需 WE 软件未装）、`@dexthemes/deepseek-harness-plugin`（主题管理）

---

## 4. 踩雷与处置（SOP 已同步 `50-taskpacks/WORK-LAB-DSH-UPDATE-SOP.md`）

| 雷 | 症状 | 根因 | 处置 |
|---|---|---|---|
| pnpm 还原陷阱 | 插件版本/颜色补丁反复回退 | market 装/卸插件触发 pnpm install → 从 lockfile 还原 | package.json 声明同步最新（update-dsh-plugins.py 内置；`^1.4.3→^1.4.8`）|
| web-search-pro | boot 崩 `Cannot find package '@anweat/dsh-browser'` | 插件代码引用未声明依赖 | 回滚（package.json bundles/deps + node_modules 清理）|
| remote-web-ui 更新卡死 | 更新 60s+ 无响应，占 in-flight 锁 600s | cloudflared 二进制下载网络不通 | 跳过（SKIP 集合）；锁超时后恢复 |
| obsidian-memory 崩溃 | boot 崩 `Cannot read properties of undefined (reading 'vaultPath')` | cordis rc.5 传 config=undefined，插件未防护 | `config = {}` 一行修复 + maintain 兜底 |
| lightningcss 二进制 | boot 崩 `Cannot find module '../lightningcss.win32-x64-msvc.node'` | 可选依赖二进制未随插件更新安装 | npm registry 手动下载 1.33.0 二进制放置（不碰布局/lockfile）|

---

## 5. 当前精确状态

- **git**：main HEAD `ad10333`（同 08-18 交接）；本轮工作 = 项目外 DSH 侧（无 WORK-LAB 提交）；**待提交 2 文件**（08-18 交接 + SUMMARY 更新，用户自审中——本轮文档加入后共 3 件待审）。
- **运行**：web PID 1976（3080 HTTP 200）；dsh-desktop 运行中（鲸鱼图标，启动即跑 maintain）；鲸吟皮肤；31 插件全最新（除 remote-web-ui）。
- **关键脚本**（`.hermes/task-runtime/`）：update-dsh-plugins.py（批量更新 + 声明同步 + 重试）、reapply-dsh-color-patch.py、start-dsh-dest.py、install-dsh-dest.py、read-head.py、om-tmp（obsidian-memory tarball 临时）。
- **残留待清理**（等指示）：项目根 `$dest/`（mingw64 误复制数百 MB）、`profiles/node_modules.mig-bak`、`profiles/web/node_modules.mig-bak2`、`profiles/web/node_modules/dsh-web-search-pro.mig-bak`（已删？确认）、`.hermes/task-runtime/om-tmp`。

---

## 6. 待办（下一步优先级）

1. **提交交接文档**（08-18 + 08-19 + SUMMARY 更新，3 件，需用户批准）
2. **主体升级 rc.5 → rc.7**（SOP §2 手动流程；先 dry-run 验证依赖树；新插件 peer 要求 rc.6+ credentials——升级会消除 codex-meter/obsidian 类 soft-incompatible）
3. **obsidian-memory vault 配置**（用户自填：侧边栏 Obsidian Memory 面板 / cordis.patch.yml / OBSIDIAN_VAULT_PATH）
4. **remote-web-ui 更新**（等网络可用时重试；cloudflared 下载）
5. 历史挂起：WL3-100/110 收编、WL-DSH-040 付费 smoke（用户填 key + 批准）、SQLite 执行核心、frontend F2/F3、native app.exe 重建、WL3-820
6. 可选：`dsh-free-search`（搜索缺口）、`dsh-vision-fallback`（视觉增强）

---

## 7. 关键决策（本轮）

- **维护自动化** = dsh-desktop 启动钩子 + 幂等脚本（不阻塞、失败降级、日志留痕）
- **颜色修复走官方变量语义**（button-primary-fill + label-primary-foreground）而非固定色（皮肤无关）
- **插件管理走官方机制**（update-checker API / dshmarket），坏插件立即回滚，卡死更新跳过（不阻塞整体）
- **obsidian-memory 装回**（用户自填 vault；E 盘不代配不访问）
- **自研融合判定：不需要**（市场 1520 插件全覆盖）
- **声明同步** = pnpm 还原陷阱根治（每次批量更新后必须）

---

## 8. 增补（2026-08-20 晚：速度/SSH/新 UI/自动恢复）

- **插件更新提速**：npm 直连限速 133KB/s → `profiles/web/.npmrc` 切 **npmmirror**（1.5MB/s，快 11 倍）；批量更新 10+ 分钟 → ~50s。.npmrc 勿配 proxy（拖慢 npmmirror）。
- **github 连接**：SSH 优先（用户 id_ed25519 已挂 github，`Hi DTALEX66!` 实测；22/443 通；`git config --global url."git@github.com:".insteadOf "https://github.com/"` 已配——pnpm github 依赖也走 SSH）；7890 代理兜底（curl -x 对 codeload 有效；market install 的 undici fetch 走 7890 会失败→新插件 SSH clone 手动装）。
- **新增 UI 插件（均源码审计过）**：`@dsh-external/dsh-client-ui-skin-maid-atelier` 0.0.1 + `open-sea-skin` 1.2.1（WebGPU 海洋）**均已安装并验证，但用户 8/20 选择 UI 精简 → 已移除 bundle 不再加载**（包保留 node_modules 备用，标题回官方）；`@dsh-external/dsh-visualize` 0.1.2（对话内生成式 UI，rc.6 peers + config 防护补丁，genui 替代——genui peer 全 rc.8 缓装）。
- **web 崩溃自动恢复（根治桌面挂）**：maintain 增强——web down 时 kill :3080 残留 → 清 task-board stale ledger 锁（PID 复用误判）→ detached spawn 重启 → 复验（实测 20.6s RECOVERED；restartWeb 已改非阻塞 spawn——spawnSync 会因 run-dsh.js 常驻卡死）。
- **残留已清理**：`$dest/`、`node_modules.mig-bak(.del)`、`web/node_modules.mig-bak2(.del)`、`om-tmp`、`newui-tmp`。
- **modlens 3.22 已更新**（rc.7 升级后 maintain --fix 自动更新成功 3.22.0——cloudflared 不再卡；全插件最新）；genui 缓装（rc.8，visualize 替代）。

- **主体升级 rc.7 完成（2026-08-20）**：source checkout `99f6f02f`（dsh-v0.1.0-rc.7）+ pnpm install --frozen-lockfile（npmmirror，5.6s；lockfile 1203 项过官方供应链策略）；node-pty 随 rc.7 升 **1.2.0-beta.15**（PR #886 官方修复内置）；36 插件全加载、soft-incompatible 消失（codex-meter rc.6+ 满足）、颜色补丁/皮肤/会话无损；origin 改 SSH；备份 `dsh-backup-2026-08-20/`（385MB，回滚 pin 47f94385）。

- **UI 精简（2026-08-20 用户决策）**：从三层叠加（whale-song 鲸吟 + maid-atelier 女仆 + open-sea-skin 海洋 iframe）精简为**只要 whale-song 鲸吟**——`data-dsh-skin-center` active、深海蓝 #081a40、女仆/海洋 bundle 移除不加载（包保留备用）；鲸鱼娘 pet 保留；按钮颜色补丁仍正确（深蓝底白字）。
