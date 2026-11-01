---
name: dsh-administration
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/dsh-administration/SKILL.md
---

---
name: dsh-administration
description: Use when maintaining DeepSeek Harness (DSH).
---

# DSH Administration（DeepSeek Harness 运维）

DSH = DeepSeek Harness（`deepseek-ai/deepseek-harness`，0.1.x-rc preview，pnpm workspace + cordis 插件架构）。WORK-LAB 受管客户端，桌面入口 = dsh-desktop.exe（Tauri 壳加载 `http://127.0.0.1:3080`）。

## 部署布局（2026-08-18 迁移后）

- **主运行体**：`D:\All projects\DSH\deepseek-harness\` = `source`（git，detached pin `47f94385`）+ `dsh-home`（profiles/web 配置 + sessions/storages + 插件）
- **桌面壳**：`D:\All projects\DSH\dsh-desktop\` = `src-tauri\`（lib.rs/tauri.conf.json/icons）+ `build-x.ps1` + `run-dsh.js`
- **旧位置**：`.hermes/task-runtime/deepseek-harness/`（迁移纪律保留，作回滚基线，勿动）
- **快捷方式**：`C:\Users\ALEX\Desktop\DeepSeek Harness.lnk` → dsh-desktop.exe
- **权威文档**：`50-taskpacks/WORK-LAB-DSH-UPDATE-SOP.md`（更新 SOP）+ `WORK-LAB-DSH-HANDOFF-2026-08-18.md`（交接）

## 架构心智模型（关键，避免误判）

- **官方核心插件**（`@deepseek-ai/*`）= **source workspace 包**（source/packages），不在 `profiles/web/node_modules` 顶层——顶层查 @deepseek-ai 显示 ENOENT 是**正常**的，不是缺失。
- **第三方插件**（`@linxin666/*`、`@a9i5k4/*`、`@anionex/*`、`dsh-*`）= `dsh-home/profiles/web/node_modules/` 下的**真实目录**。
- 插件全 pending + `@file: ... file not found` = `profiles/web/node_modules` 结构损坏（空壳目录树），不是网络/配置问题。

## 三层更新机制

### 1. 插件更新（官方 API，推荐）

- 内置 **dsh-update-checker** 插件（`POST /dsh-update-checker/plugin-update`，body `{"name":"<插件名>","confirm":true}`）。
- **`confirm:true` 必带**（writeGate 强制）；仅 loopback（127.0.0.1）可调；单飞锁 600s。
- 自动备份（`.dsh-plugin-backups`）+ 回滚接口（`plugin-rollback`）+ 重启看门狗（`/restart`）。
- 批量脚本：`.hermes/task-runtime/update-dsh-plugins.py`（读 plugins.json → 逐个更新，dsh-update-checker 自身排最后）。
- **长任务必须后台跑**（2026-08-20 实测）：一次批量更新 20 个插件 = 20-40 分钟，**execute_code 5 分钟超时会杀进程**且留下孤儿 npm 子进程占锁 → 用 `terminal(background=true, notify_on_complete=true)` 跑；DSH 侧脚本（`dsh-maintain.js` 等在项目外）用 `.hermes/task-runtime/run-maintain.py` 绕行 wrapper 边界（`python run-maintain.py --fix`）。被杀后先清孤儿（npm-cli/cloudflared 进程）再重启 web 清锁。
- **坑**：`plugins.json?fresh=1` 触发强制 npm 重扫（慢，>40s），脚本超时会**误报 0 个可更新**——用不带 fresh 的缓存端点（默认 6h 自动复查）。
- 每插件约 2-3 分钟（npm 下载+临时目录安装+拷贝+依赖核对），22 个约 40-60 分钟。
- **更新慢的根治（2026-08-20 实测，用户点破「插件不可能几百MB」）**：慢的主因是 **npm registry 直连被限速（~133KB/s）**，不是插件大。两件套：
  ① `profiles/web/.npmrc` 设 `registry=https://registry.npmmirror.com`（**实测 1.5MB/s，快 11 倍**；批量 9 插件从 10+ 分钟降到 ~50s）。**去 proxy 行**——`.npmrc` 的 proxy 影响**所有** npm 请求（含 npmmirror，反而慢）；cloudflared 类 postinstall 下载走的是 web 进程 env 的 `HTTPS_PROXY`（见下），与 `.npmrc` 无关。
  ② **git github→SSH**：`git config --global url."git@github.com:".insteadOf "https://github.com/"`（本机有 `~/.ssh/id_ed25519` 且已挂 github，`ssh -T git@github.com` 得 `Hi DTALEX66!`；22/443 直连通）——pnpm 的 github: 依赖 clone 也走 SSH，快且稳。
- **market install 的 fetch 失败（2026-08-20 实测）**：dshmarket 的 install/uninstall **fetch 会读 web 进程 env `HTTPS_PROXY`** → 走 7890（CC Switch）→ 对 github.com 网页返回失败 `fetch failed (0s, 2 attempts) · tried through the configured proxy`（curl -x 7890 却通——undici CONNECT 与 curl 行为不同）。绕行：**SSH clone 手动装**（`git clone git@github.com:<owner>/<repo>.git` 到 `.hermes/task-runtime/` → 取包（monorepo 子目录如 `maid-atelier/`）→ 复制到 `node_modules/<包名>` → package.json `dependencies` + `dsh.profile.bundles` → 重启）。大仓库 SSH clone 也会卡（open-sea-skin 43MB）→ 用 `curl -x http://127.0.0.1:7890 -L codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main`（用户授权代理下载时）。

### 2. 主体更新（source 部署，手动 git SOP）

- **官方 npm 更新对 source 克隆部署无效**：status.json 实测 `installed:null`（它检测 npm 全局/项目安装，source 克隆检测不到）。
- SOP：备份 dsh-home（robocopy，排除 node_modules；实测 385MB）→ 停 web → `git fetch origin` → checkout 目标 commit（保持 detached pin）→ `pnpm install --frozen-lockfile`（source 根）→ 启动 → 验证插件 → 颜色补丁重打。
- 回滚：checkout 旧 commit + 恢复备份。
- **2026-08-20 rc.7 升级实测（rc.5 `47f94385` → rc.7 `99f6f02f` 已完成）**：
  - source 是 **partial clone（`remote.origin.partialclonefilter=blob:none`）**——checkout 新 commit 缺对象时自动从 promisor remote fetch。**`git -c http.proxy=7890 fetch` 报 `remote username contains invalid characters`** = origin URL 被全局 insteadOf 重写搞乱 → 直接 `git remote set-url origin git@github.com:deepseek-ai/deepseek-harness.git`（SSH 直连，**无需代理**）→ `git fetch origin --filter=blob:none` → `git checkout 99f6f02f`（`describe --tags` = `dsh-v0.1.0-rc.7`）。
  - **pnpm 重建**：`corepack` 不在 PATH（python subprocess FileNotFoundError）→ 用 `.hermes/task-runtime/run-pnpm.js`（内部 `node <nodeDir>/node_modules/corepack/dist/corepack.js pnpm@11.7.0 <args>`）；source 根 `.npmrc` 设 `registry=https://registry.npmmirror.com` 加速（lockfile integrity 不受 registry 影响）→ `pnpm install --frozen-lockfile` **5.6s**（lockfile 1203 项过官方供应链策略）。
  - rc.7 依赖树自带 **node-pty 1.2.0-beta.15**（PR #886 官方修复内置）——profiles/web 的 1.1.0 补丁仍由 maintain 兜底，随 better-sidebar 更新会自然升级。
  - 升级后验证：36 插件全加载、**soft-incompatible 消失**（codex-meter rc.6+ 满足）、**modlens 3.22.0 也更新成功**（此前 cloudflared 卡——rc.7 + 代理 env 后通）、颜色补丁/皮肤/会话无损。
- **profiles/web/node_modules 禁止手动 pnpm install**（防空壳红线，见坑 1）。

### 3. 桌面壳（Tauri 2.11.5）

- **窗口图标 API（实测踩坑）**：`tauri::Builder` **没有** `.icon()` / `.default_window_icon()` / `.set_default_window_icon()`（后者在 `Context` 上，不是 Builder）。正确做法：
  ```rust
  use tauri::Manager;
  tauri::Builder::default()
      .setup(|app| {
          if let Some(win) = app.get_webview_window("main") {
              win.set_icon(tauri::include_image!("icons/icon.png"))?;
          }
          Ok(())
      })
      .run(tauri::generate_context!())
  ```
  `include_image!` 路径相对 `CARGO_MANIFEST_DIR`（src-tauri/）。tauri.conf.json 的 `app.windows[].icon` 字段 **schema 不允许**（不要加）。
- **构建**：`powershell -File "D:\All projects\DSH\dsh-desktop\build-x.ps1"`（增量 ~24s）。前置：SUBST `X:` → dsh-desktop（重启后需重建）+ rust GNU toolchain + 修好的 `~/.cargo/config.toml`。产物直接写 `X:\src-tauri\target\release\`（SUBST 映射）。

### 4. 打开桌面自动维护（dsh-maintain.js，2026-08-19 起生效）

- dsh-desktop（main.rs `ensure_dsh_maintenance`）启动时 **detached spawn** `node dsh-maintain.js --fix`（cwd=`D:\All projects\DSH`），不阻塞 UI、失败不影响启动。
- 自动执行（幂等）：① 颜色补丁缺失即重打（背景 `button-primary-fill` + 文字 `label-primary-foreground`，两替换独立检查——勿用"`#fff` 不存在就早退"的逻辑，会跳过背景升级）② **obsidian-memory config-undefined 崩溃修复**（`config = {}` 默认参数，见插件审计段）③ 原生二进制缺失自动下载修复（lightningcss 类）④ 插件有可更新 → 走官方 API 批量更新（dsh-update-checker 排最后）→ 更新后重打补丁 + 重启 web ⑤ **web 崩溃自动恢复**（2026-08-20 增强，根治"桌面挂"）：`checkPlugins` 失败（http 0）→ `killWebProcess()`（netstat :3080 找残留 PID → taskkill /F /T）→ `clearStaleLedgerLock()`（删 `dsh-home/task-board/ledger-v2.lock`——web down 时无合法持有者，删安全）→ `restartWeb()` → 5s 后复验 → `RECOVERED`。实测：杀 web + 种 stale 锁 → `--fix` **20.6s 闭环**（`web: DOWN → stale ledger-v2.lock removed → restarting → RECOVERED (healthy)`）。
- 手动：`node D:\All projects\DSH\dsh-maintain.js --check`（只查不改）/ `--fix`（修复）；日志 `D:\All projects\DSH\dsh-maintain.log`（每次打开留痕，可追溯）。
- **主体升级已执行（2026-08-20：rc.5 `47f94385` → rc.7 `99f6f02f`）**——完整执行经验见 §2 更新后段落（partial clone + origin 改 SSH + corepack 经 run-pnpm.js + npmmirror 加速）。后续跨版本升级仍按 §2 SOP：先备份（robocopy dsh-home → `.hermes/task-runtime/dsh-backup-<date>/`，排除 node_modules）再动，回滚 = checkout 旧 pin + 恢复备份。

## 皮肤（skin-center，2026-08-19 实测）

- **机制**：皮肤 = body attr（`body[data-dsh-<id>]`）+ CSS 注入（皮肤 bundle 注册，`\0dsh-css:packages/skins/<id>/src/client/<id>.module.css.mjs`）。**单独 `setAttribute` 无效**（CSS 未挂载，需皮肤中心激活流程）。
- **应用 API**：`POST /api/skin-center/apply` body **`{"skin":"<皮肤id>"}`**（不是 `{name}`/`{id}`，错 key 返回 `invalid-skin: pass a skin name or official: true`）；返回 `{ok:true, active:"<id>", message:"…refresh to see it"}` → 刷新页面生效。`{"official":true}` 还原官方皮。
- **皮肤列表（12 个，资产在 `@linxin666/dsh-skins/skins/`，注册表在 skin-center）**：`whale-song`（鲸吟，深蓝 #081a40 底+浅蓝 #d8e5f5 字）、`blue-fantasy`（蓝幻想）、`harbor`（夕港）、`maid-atelier`（深海女仆工坊）、`matrix`/`miku`/`minecraft`/`trading`/`whale-mom`/`xp`/`dragon-heir`。
- **dshmarket `use-skin` 不适用于资产皮**：`POST /dsh-market/use-skin` body `{name}` 要求**市场 installed 记录**（对 dsh-skins 资产皮报 `not an installed theme`）→ 换皮一律走 **skin-center `/api/skin-center/apply`**。
- **验证**：console 查 body computed `backgroundColor:rgb(8,26,64)` + `color:rgb(216,229,245)` = whale-song 生效（vision 模型不可用时用 computed style 验证）。
- **独立皮肤插件（非皮肤中心注册表，2026-08-20 实测 maid-atelier 深海女仆工坊）**：有些皮肤是**独立 npm 包**（`@dsh-external/dsh-client-ui-skin-maid-atelier`，cordis.patch.yml `insert: id/name` + client.js `apply()` 设 `data-dsh-maid-atelier` + 内嵌 webp 资产）——**不注册皮肤中心**（`/api/skin-center/apply` 报 not found），**加载即生效**（bundle 激活）。验证：页面标题变皮肤名（如「深海女仆工坊 · DeepSeek Harness」）+ body 有 `data-dsh-maid-atelier` + 内嵌 `data:image/webp` 图片挂载。与皮肤中心皮（whale-song）是独立覆盖层，可共存。
- **open-sea-skin 类（动态 WebGPU 皮肤）**：仓库 43MB（extension/site/docs 占了大部分）——**只装运行时**：`plugin/`（index.js `inject:['webServer']` 提供 `/open-sea-skin` 静态路由）+ `native-dist/`（loader.js/ocean.js/three.webgpu.js/字体/skin.html，~1.1MB）→ `node_modules/open-sea-skin` + bundle 注册。生效信号：页面出现「海洋皮肤设置」按钮 + iframe `__open-sea-skin__`（src=`/open-sea-skin/skin.html?skin=1&sea=45&auto=1`）。HTTP 路由 `GET /open-sea-skin/*` 200。
- **UI 精简/换肤决策（2026-08-20 用户明确选择）**：三层叠加（skin-center 皮 + 独立皮肤插件 maid-atelier + WebGPU 海洋 iframe + pet 鲸鱼娘）**视觉过重**——用户选「**只要 whale-song 鲸吟**」轻量单层。**卸载不删模式**：从 package.json `dsh.profile.bundles` 移除插件名 + `dependencies` 移除声明 → 重启 web → 不再加载（标题回官方「DeepSeek Harness」、iframe/webp 归零）；**node_modules 包体保留（~1.1MB）作备用**——想换回只需 bundle 加回。**判定当前加载了什么 UI 层的 console 配方**：`bodyAttrs`（`data-dsh-skin-center`=皮肤中心皮 / `data-dsh-maid-atelier`=独立皮肤层）、`document.querySelectorAll('iframe[src*="open-sea"]')`（海洋 iframe）、`img[src^="data:image/webp"]`（独立皮肤内嵌资产计数）、`getComputedStyle(body)`（bg/color 配色，whale-song=rgb(8,26,64)/rgb(216,229,245)）。**用户偏好**：皮肤保持单层轻量，勿默认叠加多层增强。

## 插件审计与市场（dshmarket，2026-08-19 实测）

- **市场注册表**：`GET /dsh-market/registry` = awesome-dsh-plugin 列表（**1520 插件/20 分类**：ui/tools/usage/vision/browser/memory/theme…；每条 `description` 是 `{en,zh}` 双语）。调研"有没有更好的插件"用它 + `registry.npmjs.org/-/v1/search?text=dsh`。
- **安装**：`POST /dsh-market/install` body **`{"url":"<registry 里该插件的 url>"}`**（是 url 不是 name；必须匹配 curated registry，否则 400）。返回含 `ok/hot/compatibility/rollbackId`；`hot:false` = bundle patch 含配置，**需重启 web 才生效**。
- **卸载**：`POST /dsh-market/uninstall` body `{"name":"<插件名>"}`；busy-agent 运行中拒绝（409）；dshmarket 不能卸载自己。
- **市场管理 vs 聚合依赖**：`GET /dsh-market/installed` 只列市场独立管理的插件；`@linxin666/dsh-web-ui-all` 全家桶的组成插件（skins / describe-image / aionui-panel 等）是它的依赖——对这些 uninstall 会报 **"plugin is not installed"**（无法独立卸载；无实际负载时可保留，如已退役的 dsh-skins）。
- **装新插件后必须验证 boot**：dshmarket/update-checker 安装**不保证装齐依赖**。2026-08-19 事故：`dsh-web-search-pro` 代码 import `@anweat/dsh-browser` 但 package.json 未声明该依赖 → boot 时 bundle include 失败 → **整个插件树加载失败、web 崩**（API 不可用，只能手动清理）。手动清理三处：① package.json 的 **`dsh.profile.bundles` 数组**（boot 插件清单，必改）② package.json `dependencies` ③ node_modules 包目录（rename 或删；**残留 `.mig-bak` 目录会被 plugins.json 扫到**，要删净）。\n- **同类变体（2026-08-19 二次踩坑，最终解法）**：`dsh-client-ui-obsidian-memory` 装后 boot 崩 `Cannot read properties of undefined (reading 'vaultPath')`——cordis rc.5 传 `config`=undefined（源码 `config.vaultPath || env` 保护在 config 本身 undefined 时无效）。**根因级修复**：`function apply(ctx, config)` → `function apply(ctx, config = {})`（默认空对象 → 无 vaultPath 时 warn+return 优雅降级，不崩 web）。该修复已内置 `dsh-maintain.js` 的 `obsidianMemoryFix`（幂等检查 bad/good 签名，`--fix` 自动重打，防 pnpm 重装覆盖）。**重装方式**：market install 若报 **pnpm EPERM**（web 占用 node_modules 文件锁）→ **手动放包绕 pnpm**：`codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main` 直连下载 tarball → 解压到 `node_modules/<包名>` → package.json `dependencies` 加 `github:<owner>/<repo>` + `dsh.profile.bundles` 补名 → 重启（**完全绕开 pnpm，不动其他包/lockfile**）。**用户配置 vault 的两种入口**：① 侧边栏 **Obsidian Memory 面板**（pickDirectory UI，存 localStorage——只影响浏览面板）② 服务端 `obsidian_memory_*` 工具需 `cordis.patch.yml` 的 `vaultPath` 或环境变量 `OBSIDIAN_VAULT_PATH` 才真正读写——**前端选目录 ≠ 服务端工具启用**，要讲清楚。\n- **插件更新卡死占锁（2026-08-19 实测）**：某插件更新卡在**原生二进制下载**（日志/进程可见 `node lib/cloudflared.js bin install`，github 直连不通）→ 占 update-checker **in-flight 单飞锁（600s）** → 后续所有插件更新返回 `plugin update already running`。处理：**杀 npm-cli/cloudflared 子进程**（`Get-CimInstance Win32_Process` 匹配 CommandLine）→ **重启 web 清锁** → 脚本 `SKIP = {该插件}` 排除重跑（`update-dsh-plugins.py` 已内置 SKIP 集合 + 失败重试：锁忙等 20s×3 / 超时空响应重试 2 次）。**根治（2026-08-20 实测，两件套缺一不可）**：① `profiles/web/.npmrc` 加 `proxy=http://127.0.0.1:7890` + `https-proxy=http://127.0.0.1:7890`（管 npm 包下载）；② **cloudflared 类 postinstall 内部下载（`node lib/cloudflared.js bin install`）不走 npm config**——必须在启动 web 的进程 env 设 `HTTP_PROXY`/`HTTPS_PROXY=http://127.0.0.1:7890`（`.hermes/task-runtime/start-dsh-dest.py` 的 env 已加）。env 生效后 remote-web-ui（cloudflared）更新成功，**不再需要 SKIP**。注意：dsh-desktop 的 `ensure_dsh_service` 是 Rust `Command::new("node")` 启动——若其 spawn env 无代理，桌面壳路径下启动的 web 更新仍会卡（更新子进程继承 web env）。
- **soft-incompatible 信号**：新插件 peer（如 `@deepseek-ai/dsh-credentials` >=rc.6）高于主体（rc.5）→ 安装成功但 `compatibility.code=soft-incompatible` / `belowMin`——功能可能受限，是**主体该升级**的信号。
- **peer 不兼容 → 找同类兼容替代（2026-08-20 用户点破「换个UI插件不完了吗」）**：插件 peer 高于主体（如 genui peer 全 `rc.8`）时，**不要只等主体升级**——先在 registry 同分类（ui/theme）找**功能同类但 peer 更低**的替代：genui（rc.8，缓装）→ **`@dsh-external/dsh-visualize` 0.1.2（peer 只要 rc.6 + 零 deps + 源码 clean + 已手动打 config 防护 `config = {}`）已装替代**（对话内生成式 UI：模型渲染交互 HTML 卡片）。决策顺序：同功能 → 低 peer → 装前审计（坑 14）→ config 防护 → 装完验证 web 不崩。
- 补缺口候选（2026-08-19/20 调研+落地）：用量/余额 `dsh-codex-meter`（**已装**，热加载生效）；搜索类 `dsh-web-search-pro`（依赖缺失失败）→ 替代 `dsh-free-search`；网页读取 `dsh-read-url`；Obsidian 记忆 `dsh-client-ui-obsidian-memory`（**已装**，重启生效；连接用户 vault 时需用户授权 E 盘路径，assistant 不主动读）；对话内生成式 UI `@dsh-external/dsh-visualize` 0.1.2（**已装**，替代 peer rc.8 的 genui）；皮肤 `@dsh-external/dsh-client-ui-skin-maid-atelier` 0.0.1 + `open-sea-skin` 1.2.1（**已装后按用户 UI 精简决策从 bundles 移除不加载，包保留 node_modules 备用**——当前皮肤 = 仅 whale-song 鲸吟）；缓装：genui（peer rc.8）、deepseek-design（rc.5 未测）；modlens 3.22 已于 rc.7 升级后更新成功（3.22.0，全插件最新）。
- 生态信号（2026-08-19 调研）：`asen-goat-mine/boujoy-harness` 等第三方基于 DSH 做前端产品（复用 DSH 事件/RPC 协议，`BOUJOY_DSH_ROOT` 指向自建 DSH）——协议层稳定；但 Windows 用户已有 dsh-desktop+UI 全家桶，无需切换（此类第三方壳多为 macOS 原生 + Windows Beta，成熟度低）。

## 坑（每条都是真金白银）

1. **防空壳红线**：`profiles/web/node_modules` 手动 pnpm/npm install → hoisted 重装把 workspace 插件链接打成**空壳目录树**（149 空目录、package.json 全无）→ "Failed to load plugins / 45 entries did not activate / file not found"。恢复：停 web → **rename（junction 安全，勿删）** node_modules → `.mig-bak<N>` → `pnpm install`（用 `.hermes/task-runtime/install-dsh-dest.py`）→ 重启 → 验证。
2. **循环 junction 删除必失败**：递归删除（rd / PowerShell / fs.rmSync 跟随 symlink）全部失败 → 用 Node `fs.renameSync` 只改名（`profiles/node_modules.mig-bak`），DSH 启动时 `healProfilesModuleFallback` 自动重建干净 junction。
3. **cargo config TOML 转义**：`~/.cargo/config.toml` 的 Windows 路径必须双反斜杠（`D:\\All projects\\...`）；单反斜杠 `\A` 是非法转义 → cargo 配置解析全挂（任何 cargo 命令失败）。
4. **windres 空格路径崩溃**：CARGO_TARGET_DIR 含空格物理路径 → `cc1.exe: fatal error`。用 SUBST 无空格路径（`CARGO_TARGET_DIR=X:\src-tauri\target`）。
5. **rust GNU toolchain 重装**：`rustup install stable-x86_64-pc-windows-gnu` 走国内镜像（`RUSTUP_DIST_SERVER=https://rsproxy.cn`、`RUSTUP_UPDATE_ROOT=https://rsproxy.cn/rustup`），装后 `rustup default`。
6. **颜色补丁（dsh-update-checker 白字白底，2026-08-19 升级到根因级）**：插件按钮**用错 CSS 变量**——背景用 `--dsw-alias-brand-primary`（品牌强调色，深色主题官方=近白 #f9fafb、鲸吟皮肤=浅蓝 #8ab4de）做按钮底 + 硬编码 `color:#fff` → 白字浅底不可读。**官方按钮语义**：背景 = `--dsw-alias-button-primary-fill`（按钮填充色，鲸吟=深蓝 #2f6fb8；官方深色=近白），文字 = `--dsw-alias-label-primary-foreground`（对比文字色，鲸吟=白、官方深色=黑）。**升级版补丁**（dsh-maintain.js 已内置，两替换独立幂等——**勿用 `if(!includes('color:#fff')) return` 早退，会跳过背景升级**）：`.dsh-update-btn-primary`/`.dsh-plugin-btn-primary` 两处 `background:var(--dsw-alias-brand-primary,#4f8cff)` → `var(--dsw-alias-button-primary-fill,#4f8cff)` + `color:#fff` → `var(--dsw-alias-label-primary-foreground,#0f1115)` → **任何皮肤/任何主题下都正确**（官方深色=近白底黑字；鲸吟=深蓝底白字）。**1.4.8 仍未修复** → 每次更新 dsh-update-checker 后重打（脚本 `.hermes/task-runtime/reapply-dsh-color-patch.py`）。**「为什么反复出现」的真正机制（2026-08-19 查清 + 2026-08-20 源码取证修正）**：dshmarket/update-checker 的 install/update 底层走 **pnpm → 从 lockfile 还原 node_modules 全部文件**（API 更新只改 node_modules 包，**不更新 package.json 的 `dependencies` 版本声明**）→ 任何后续 pnpm 操作（如市场装新插件）把已更新的包（1.4.8→1.4.3）和补丁**一起还原**。（2026-08-20 源码取证修正：全树还原实际来自 **dshmarket** 的 pnpm add/remove；**update-checker v1.4.3+ 走临时目录 npm 安装+拷贝**、不直接对 profiles 跑 npm，且 **v1.4.6 起官方已自动把新版本写回 package.json + 同步 lockfile**（`pnpm install --lockfile-only`）——见「官方来源与证据地图」）**底层机制（2026-08-20 调研，pnpm/pnpm#753 zkochan 本人）**：node_modules 与内容寻址 store 是**硬链接**——直接改 node_modules 文件 = 改 store → pnpm 校验发现 store hash 与预期不符 → `WARN Refetching ... to store, as it was modified` 从 registry 重新下载还原。**官方方案**：不要直接改 node_modules，用 `pnpm patch <pkg>` + `pnpm patch-commit` → `patchedDependencies`（v11 起必须写 `pnpm-workspace.yaml`，package.json 的 `pnpm` 字段已弃用）；patch-package 在 pnpm 上冗余（官方 README 明示）。**当前策略**：maintain 启动自动重打（颜色/obsidian/node-pty 三补丁）已够用；后续可迁移 pnpm patch 机制根治（建议随主体 rc.7 升级一并做）。**彻底修复三件套**：① 批量更新脚本 `update-dsh-plugins.py` 已内置**自动同步 package.json 声明**（npm 范围依赖写回 `^<installed>`；github:/file: 源保留原声明；单更插件时手动同步 `dsh-update-checker: ^1.4.3` → `^1.4.8`）② 重打补丁 ③ dsh-maintain.js 启动自愈兜底（任何还原后下次打开自动重打）。验证：console 查 `.dsh-update-btn-primary` computed = `color:rgb(255,255,255)` on `background:rgb(47,111,184)`（鲸吟下深蓝底白字=修好）；官方深色下应为 `rgb(15,17,21)` on `rgb(249,250,251)`。
7. **图标空壳**：图标文件"纯白/1 量化色"= 损坏（透明+图形全丢），不是正常图标。用官方 `source/apps/web/public/favicon.svg`（鲸鱼 logo）→ cairosvg 白色化（SVG 里 path 自带 `fill="#000"`，替换它）→ PIL 合成品牌蓝圆角背景 → 全套尺寸 + icon.ico（脚本 `.hermes/task-runtime/gen-dsh-icons.py`）。
8. **插件更新后原生二进制缺失**：批量插件更新后 web 起不来，日志 `Cannot find module '../lightningcss.win32-x64-msvc.node'` —— update-checker 依赖合并升级共享依赖（如 lightningcss 1.32→1.33）但可选二进制包没随装。修复：npm registry 下载**同版本**二进制 tarball → 解压 `.node` → 放置（绕过 install，不碰布局/lockfile）→ 重启。**不是** node_modules 结构损坏，勿 rename 重装整树。详见 `dsh-runtime-ops`。
9. **market install pnpm EPERM**：web 运行中 dshmarket 安装偶发 `ERR_PNPM_EPERM`（pnpm 想替换被 web 进程占用的 node_modules 文件）→ **手动放包通道**（绕开 pnpm，不动其他包/lockfile）：github `codeload.github.com/<owner>/<repo>/tar.gz/refs/heads/main` **直连可用**（无需代理）→ 解压到 `node_modules/<包名>` → package.json `dependencies`（`github:<owner>/<repo>`）+ `dsh.profile.bundles` 补名 → 重启 web。注意：手动放的包不在 market installed 记录（uninstall 报 not installed），后续 pnpm install 可能从 github 源重装并覆盖文件级补丁——所以补丁类修复要挂进 dsh-maintain.js 兜底。
10. **web 崩溃读日志要找「根因 Error」，不是最后一个 Error**（2026-08-20 实测）：启动失败时日志尾部可能只显示**表象堆栈**（如 `node-pty ... AttachConsole failed`——conpty 辅助进程在无控制台上下文的噪音），真正的根因在上方一行：`Error: dsh: plugin tree failed to load: ... task-board ledger is already owned by process <pid>`。**先搜 `plugin tree failed to load` 那一行**再决定处置。
11. **task-board ledger 锁残留 + Windows PID 复用误判**（2026-08-20 实测）：web 异常退出后 `dsh-home/task-board/ledger-v2.lock` 残留（记录旧 web 的 pid）；Windows 很快复用 PID（如 1976 → SearchFilterHost.exe）→ 新 web boot 时 `processIsAlive(pid)` 误判锁仍被占用 → 整个插件树加载失败、web 起不来。**处置**：确认 3080 无活跃 web → 读锁文件确认 pid 非当前 DSH 进程 → 删 `dsh-home/task-board/ledger-v2.lock`（ledger-v2.json 任务数据**保留**）→ 重启 web。**先查 3080 监听**再删锁，避免双写。**已自动化（2026-08-20）**：`dsh-maintain.js --fix` 的 `ensureWebUp` 在 web down 时自动 kill 残留 → 清 stale 锁 → 重启 → 复验（无需手动处置）。
12. **桌面壳「窗口在但标题空/白屏」= web 挂了**（2026-08-20 实测）：`Get-Process dsh-desktop` 显示 Responding=True 但 `MainWindowTitle` 空 → dsh-desktop 进程活着但 `http://127.0.0.1:3080` 没起来（Tauri webview 无内容）——查 `netstat :3080`，先修 web（见坑 10/11），再重启壳加载最新状态。
13. **bundle 名必须带 scope（2026-08-20 实测）**：手动装 scoped 插件包（`@scope/pkg`）时，`dsh.profile.bundles` 数组必须写**完整带 scope 的名字**（如 `@dsh-external/dsh-client-ui-skin-maid-atelier`）——写无 scope 的短名（`dsh-client-ui-skin-maid-atelier`）会 boot 崩 `cannot resolve profile bundle "..." from the dsh installation or profiles/web`（`resolveBundleDir` 按 bundle 名找 node_modules 顶层，scoped 包在 `@scope/` 子目录找不到）。对比参考：`@linxin666/dsh-web-ui-all` 等既有 scoped bundle 都带 scope；无 scope 包（dsh-update-checker 等）才用短名。
14. **装插件前必须源码审计（2026-08-20 用户硬性要求：「确保插件的安全风险，审计下源码，不会造成我的电脑问题」）**——流程（手动放包/SSH clone 场景必做）：① package.json 看 deps/scripts（postinstall/preinstall 恶意命令）/peerDeps（**peer 全 rc.8 vs 主体 rc.5 = 兼容风险信号，缓装**——obsidian-memory 先例崩 web）；② 敏感 API 扫描 lib/（child_process、fs 写、网络 fetch、process.env/凭据、eval）——**vendor 大库命中正常**（three.js 等知名库内部有 worker/网络加载代码），要区分「vendor 库」vs「自有逻辑」；③ 集成/安装脚本确认写哪些路径（手动触发的 `update-harness.mjs` 类安全，自动 postinstall 写系统路径要警惕）；④ 纯皮肤插件（无 deps + peer 仅 cordis）= 低风险。审计通过才装，装完立即验证 web 不崩。
15. **spawnSync 等常驻子进程 = 永久阻塞（2026-08-20 实测）**：`dsh-maintain.js` 的 `restartWeb()` 最初用 `spawnSync("node", [run-dsh.js...])`——run-dsh.js 是**常驻启动器**（spawn 完 web 不退出）→ maintain 卡死 180s+（execute_code 超时杀的是外层 python，maintain 卡在 spawnSync 不退）。**修复**：`spawn(..., {detached:true, stdio:"ignore"})` + `child.unref()` 非阻塞返回。教训：**任何"启动长驻进程"的脚本必须 spawn 不能 spawnSync**（除非明确知道子进程会退出）。
17. **node-pty 1.1.0 AttachConsole 崩溃（2026-08-20 调研+根治，microsoft/node-pty#952）**：kill() 竞态——`conpty_console_list_agent` fork 完成时 shell 已退出 → `AttachConsole(死pid)` 失败 → **agent 源码无 try/catch 直接抛未捕获异常崩溃**（无控制台进程实测 15 轮 14 次崩；前台 4/15 也崩）。官方修复 PR #886（已合入 main，**v1.2.0-beta.11+ 内置**）：agent try/catch 失败返回空列表 + `windowsPtyAgent._getConsoleProcessList` 对 `_innerPid<=0` 直接 resolve（不 fork agent）。**本机已手动打补丁**（`profiles/web/node_modules/node-pty/lib/conpty_console_list_agent.js` + `lib/windowsPtyAgent.js` 两文件）+ **maintain `nodePtyFix()` 自动重打兜底**（防 pnpm 还原；幂等标记 `try {` / `if (this._innerPid <= 0) {`）。升级替代：下次 better-sidebar 更新时 node-pty 升 1.2.0-beta.11+ 则官方修复内置。web 崩溃排查时若日志尾部是 `node-pty ... AttachConsole failed`，先按坑 10 找上面的真正根因（常是 task-board 锁或插件树），node-pty 只是表象噪音。\n18. **web「启动 busy 期」探测会误判 DOWN（2026-08-20 实测）**：web 启动后头 10-15s 在做 boot + 会话恢复（restoreLastAgent 等）——此时 `curl`/`urlopen` 探测 3080 会超时（误判「又崩了」），但进程活着（CPU 累积 + `Responding:True` + 内存正常），几秒后三端点（`/`、plugins.json、/open-sea-skin/skin.html）全 200。**判据**：先查 `Get-CimInstance Win32_Process`（进程在不在）+ `netstat :3080`（LISTENING 在不在）再下结论；maintain 的 `checkPlugins` httpGet 60s 超时是合理窗口，不要把它调成 10s。
16. **Windows 下 spawn node 必弹 CMD 窗口（2026-08-20 用户投诉「为什么老显示各种CMD终端窗口，不能直接静默吗」根治）**：node.exe 是**控制台程序**（console subsystem）——从 GUI 进程（Tauri 壳）spawn node 时不设 `CREATE_NO_WINDOW`，Windows 就为它新建控制台窗口（启动/维护时反复弹黑窗）。**三处全改才静默**：① `dsh-desktop/src-tauri/src/main.rs`：两个 `Command::new("node")` 链加 `.creation_flags(0x0800_0000)`（CREATE_NO_WINDOW），需 `use std::os::windows::process::CommandExt;` + `const CREATE_NO_WINDOW: u32 = 0x0800_0000;`——**坑：`#[cfg(windows)]` 属性不能内联在方法链中间（`error: expected identifier` 编译失败），无条件调用即可**（该项目仅 Windows）；② `run-dsh.js`：spawnSync 加 `windowsHide: true`；③ `dsh-maintain.js`：**所有** spawnSync/spawn 加 `windowsHide: true`（killWebProcess 的 netstat/taskkill、nativeBinaries 的 curl/tar、restartWeb 的 spawn）。改完 `run-build-x.py` 重建 exe（增量 ~8s；SUBST X: 重启电脑会丢需重建）。**连带坑**：maintain 的 restartWeb 最初 `stdio:"ignore"` → web 崩溃日志被丢弃（run-dsh.js 的 spawnSync inherit 继承 null stdio）→ **web 反复崩时日志无痕**，难定位（2026-08-20 web 多次无痕崩溃）。**已永久修复**：restartWeb 改 `stdio: ["ignore", webLog, webLog]`（`fs.openSync(DSH_ROOT/dsh-web-run.log, "a")`）——崩溃有痕，日志在 `D:\All projects\DSH\dsh-web-run.log`。

## 官方来源与证据地图（2026-08-20 调研，一次取证）

- **仓库身份**：`deepseek-ai/deepseek-harness`（**不是** `deepseek-ai/dsh`，后者 404；npm 包名才是 `@deepseek-ai/dsh`）。该仓库 **issues 禁用（has_issues:false）、Discussions 为 0**——核心仓库 docs/ 全树无插件更新/市场文档（git trees 递归取证）。插件更新机制的真实权威来源 = **两个社区插件仓库**：
  - 更新器 `Airmetro/dsh-update-checker`（npm `dsh-update-checker`，README changelog 即官方行为文档；issue #1-#7）
  - 市场 `dsh-market/dsh-market`（npm `dshmarket`；issue #18/#20/#39/#83/#119/#122/#130/#162/#199/#222/#223）
- **cordis.patch.yml = 官方补丁层（组合/配置层，非文件层）**：`$DSH_HOME/profiles/<name>/cordis.patch.yml` 由加载器**每次启动重放 + HMR ~1s 生效**；支持 `- id: X`+`disabled: true|false`+`config: {...}` 与 `- insert:` 装载行；**改不了包内 JS/CSS**。dshmarket 热禁用/启用走这层（#130，移植自 Noob-stupid/dsh-plugin-hub）。
- **pnpm 全树还原 = dshmarket 行为（非 update-checker）**：update-checker v1.4.3+ 的 plugin-update 走**临时目录 npm 安装+拷贝**（lib/index.js R26 注释"绝不直接对 profiles 执行 npm"）；dshmarket install/uninstall 才在 profile 上直接跑 pnpm add/remove → 按 lockfile 从 store 硬链接重放整树（官方证据：#83 "pnpm replays the whole tree"、#119 store tmp 孤儿、#222 re-extract 原始包 + ERR_PNPM_PATCH_FAILED）。
- **600s 锁官方实现**（v1.4.9 lib/index.js:2511）：`pluginUpdateInFlight && Date.now()-pluginUpdateStartedAt < 600000 → 409 "plugin update already running"`；**进程内存布尔量（重启 web 即清锁）**；600s 是"接管"不是"杀进程"（v1.3.0 changelog "10-minute takeover timeout"）；Airmetro 仓库无锁相关 issue。
- **"更新后被还原"的官方修复 = update-checker v1.4.6**：更新/回滚后把新版本写回 profile 的 package.json + `pnpm install --lockfile-only` 同步锁文件——与本部署"彻底修复三件套"① 完全一致（官方出处补全）。
- 完整取证（代码行号/issue 正文摘录）：`references/plugin-update-mechanism-research.md`

## 验证套路

- 插件加载：浏览器 `http://127.0.0.1:3080`（任务看板/技能中心/会话树在 = 核心插件活）+ `curl /dsh-update-checker/plugins.json`（29 插件清单正常，2026-08-19 批量更新后全部最新）。
- 窗口图标：PowerShell `WM_GETICON`（SMALL/SMALL2）→ 512×512/7 量化色 = 鲸鱼图标生效（class icon `GetClassLongPtr` 恒 0 属正常——set_icon 设的是实例图标）。
- junction 区：Node `fs.lstatSync` 计数 symlink（Python is_symlink 不识别 junction）。
- 启动：`.hermes/task-runtime/start-dsh-dest.py`（HTTP 200 验证）。

## 相关文件

- 更新 SOP：`50-taskpacks/WORK-LAB-DSH-UPDATE-SOP.md`
- 交接文档（最新权威）：`50-taskpacks/WORK-LAB-DSH-HANDOFF-2026-08-19.md`（自动维护+颜色根治+插件治理）；历史：`WORK-LAB-DSH-HANDOFF-2026-08-18.md`（迁移+桌面版）
- 运维脚本：`.hermes/task-runtime/`（start-dsh-dest.py / install-dsh-dest.py / update-dsh-plugins.py / reapply-dsh-color-patch.py / gen-dsh-icons.py / run-build-x.py / run-pnpm.js / run-dsh.js）+ **DSH 根 `dsh-maintain.js`**（桌面启动自动维护）


## 合并来源: dsh-runtime-ops (2026-08-21 合并优化)

---
name: dsh-runtime-ops
description: "Use when DSH plugins fail to load or its runtime breaks."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
metadata:
  hermes:
    tags: [dsh, deepseek-harness, runtime, plugins, pnpm, junction, tauri, desktop, migration]
    related_skills: [desktop-build-verification, windows-project-runtime-relocation, windows-runtime-state-recovery]
---

# DSH (DeepSeek Harness) Runtime Operations

## When to Use

- DSH web/desktop shows **"Failed to load plugins"** / all plugins `pending (waiting for services: slots, layout, ...)` / `@file:` context warnings "file not found"
- `dsh-home/profiles/web/node_modules` breaks (empty-shell dirs, junction links gone, key `@deepseek-ai/*` packages missing)
- Relocating / migrating the DSH runtime to a new root (e.g. user-approved `D:\All projects\DSH`)
- Maintaining the dsh-desktop Tauri shell (rebuild, window/exe icons) — build details live in `desktop-build-verification` §7l

Do NOT use for: WORK-LAB workflow/control-plane tasks, Hermes config, or non-DSH client runtimes.

## Runtime Layout (post-2026-08 migration, authoritative)

```
D:\All projects\DSH\
├── deepseek-harness\          # main runtime: source@<upstream pin> + dsh-home full copy
│   └── dsh-home\profiles\web\node_modules\   # DSH-MANAGED link structure (see discipline below)
├── dsh-desktop\               # Tauri shell: build-x.ps1, src-tauri\{src,icons,target}, run-dsh.js
└── run-dsh.js                 # backend auto-start script (node, stdlib only)
```
- Desktop entry = **dsh-desktop.exe only** (user ruled out the VBS launcher). It embeds `ensure_dsh_service`: if `127.0.0.1:3080` is not listening it spawns `node run-dsh.js deepseek-harness/source deepseek-harness/dsh-home web`.
- Web UI = `http://127.0.0.1:3080` (loopback). Old location `.hermes/task-runtime/deepseek-harness/` stays untouched as rollback baseline.
- DSH API key is entered by the user in the UI; never read/print it.

## Critical Discipline (do not break this again)

**NEVER run `pnpm install` manually inside `dsh-home/profiles/web`.** That directory is a DSH-managed link structure (workspace plugin links into the source tree). A manual hoisted reinstall replaces the links with an **empty-shell tree** (real dirs, no `package.json`, `@deepseek-ai` packages missing) → every plugin fails to load with "file not found". Plugin management goes through the DSH UI (plugin center / skill center). Same rule applies to any DSH-managed `profiles/*/node_modules`.

## Plugin Load Failure — Diagnosis & Repair

Symptom: web console/boot shows `45 entries did not activate` + `@file:` ... `file not found` for every plugin; page may still render if the failure is partial.

Diagnosis order:
1. Who owns port 3080 (`netstat -ano | grep :3080` + parent chain via `Get-CimInstance Win32_Process`). Confirm it launched from the correct new root (`run-dsh.js deepseek-harness/source deepseek-harness/dsh-home web`, cwd = DSH root).
2. Inspect `profiles/web/node_modules`: count top-level entries, symlinks vs real dirs (Node `fs.lstatSync().isSymbolicLink()` — junction shows as symlink), and whether key packages resolve (`@deepseek-ai/dsh-client-ui-layout`, `dsh-client-app-shell`, `linxin666/*` → `package.json` exists).
3. If `@deepseek-ai` has ~3 entries when the source shared dir has ~70, and deps like `typescript`/`vite` have no `package.json` → **empty-shell corruption** (someone pnpm-installed or a link heal failed). Repair below.
4. If the page renders fully (session tree, 任务看板, 技能中心, pet, update banner) AND the web log shows plugin `ready` lines → plugins are actually active; do not chase junction counts.

**Variant — crash right after installing/updating a plugin** (2026-08-19, validated): web dies at boot with a `failed to import loader entry ... Cannot find package '<something>'` error, and `dsh-market` API is unreachable because the web process is gone. This is NOT empty-shell corruption — the just-installed plugin referenced an **undeclared dependency** (its bundle include imports a package missing from its `package.json` and not installed). Do not rename/reinstall node_modules. Clean up manually: remove the plugin from `profiles/web/package.json` **`dsh.profile.bundles`** (the boot plugin list — the critical one) AND `dependencies`, delete its node_modules dir (and any `.mig-bak` remnant — the updater scans those too), then restart. Details in `dsh-administration` §插件审计与市场.

**Variant 2 — crash with `Cannot read properties of undefined`** (2026-08-19, validated): `dsh-client-ui-obsidian-memory` boot-crashed with `Cannot read properties of undefined (reading 'vaultPath')` — **cordis rc.5 passes `config` = undefined**; the plugin's own `config.vaultPath || env` guard can't help when `config` itself is undefined. Same manual cleanup three-part fix. Plugins requiring a **mandatory config value at boot** (like a vault path) may be unusable until configured — if the config target is a protected location (E: drive) and the user hasn't authorized it, uninstall rather than configure.

**Variant 3 — plugin update hangs and holds the in-flight lock** (2026-08-19, validated): an update stuck on a native-binary download (`node lib/cloudflared.js bin install`, GitHub direct unreachable) holds update-checker's 600s single-flight lock → every subsequent update returns `plugin update already running`. (Lock semantics, verified in v1.4.9 `lib/index.js:2511`: `pluginUpdateInFlight && Date.now()-pluginUpdateStartedAt < 600000 → 409`; it's a **process-memory boolean** — a web restart clears it; the 600s window is a *takeover* rule, not a process kill, so the hung child must be killed manually; official changelog v1.3.0 names it "10-minute takeover timeout". Full evidence: `dsh-administration` → references/plugin-update-mechanism-research.md) Fix: kill the npm-cli/cloudflared child processes (match CommandLine via `Get-CimInstance`), restart web to clear the lock, then exclude that plugin (`SKIP` set in `update-dsh-plugins.py`) and re-run. **Permanent fix (2026-08-20, validated):** two pieces, both required — ① `profiles/web/.npmrc` gets `proxy=`/`https-proxy=http://127.0.0.1:7890` (npm package downloads), AND ② the web-launching process env must carry `HTTP_PROXY`/`HTTPS_PROXY` (e.g. `start-dsh-dest.py` env) — **cloudflared's postinstall fetch does NOT read npm config**. With the env set, `@linxin666/dsh-remote-web-ui` (cloudflared) updated successfully and the SKIP became unnecessary. Caveat: `dsh-desktop`'s `ensure_dsh_service` spawns web via Rust `Command::new("node")` — its env needs the proxy vars too, or desktop-launched web updates still hang.

Repair (validated 2026-08):
1. Kill the web process tree (listen PID + parent `run-dsh.js`), confirm 3080 free.
2. Rename the broken `profiles/web/node_modules` → `node_modules.mig-bak2` (rename, never recursive-delete — see junction pitfall).
3. Rebuild deps with the project's install script pattern (source `--frozen-lockfile` + web `install` via `corepack pnpm@11.7.0` per-invocation; `cpu-features` optional failure is harmless).
4. Restart web; verify HTTP 200, page snapshot (session tree / 任务看板 / update banner), and plugin `ready` log lines.
5. The update-checker banner ("知道了 / 确定 / 不再提示") must show readable button text — that also proves the color patch below is live.

Full transcript and evidence chain: [`references/dsh-plugin-recovery.md`](references/dsh-plugin-recovery.md).

## Plugin Update Side-Effect: Missing Native Binary (2026-08-19, validated)

Symptom: after a **batch plugin update**, `web` fails at boot with
`Error: Cannot find module '../lightningcss.win32-x64-msvc.node'` (Require stack → `profiles/web/node_modules/lightningcss/node/index.js`). The web process may be dead (`Get-Process -Id <pid>` empty), and `plugins.json` returns empty (routes never registered).

Root cause: the update-checker dependency merge upgraded a **shared dep** (lightningcss 1.32.0 → 1.33.0) but its optional-dependency binary package (`lightningcss-win32-x64-msvc`) did not land → `.node` missing → boot crashes. Not a node_modules structural break — do NOT rename/reinstall the whole tree.

Fix (validated; bypasses install, does not touch layout/lockfile):
1. Read `<pkg>/node/index.js` require line for the expected `.node` filename (e.g. `../lightningcss.win32-x64-msvc.node`).
2. `curl -s https://registry.npmjs.org/<binary-pkg>/<version>` → take `dist.tarball` (e.g. `lightningcss-win32-x64-msvc@1.33.0` — version MUST match the main package).
3. Download tarball → extract the `.node` member (Python `tarfile`) → place at `profiles/web/node_modules/<pkg>/<expected-filename>`.
4. Restart web (`start-dsh-dest.py`) → verify HTTP 200 + `plugins.json` returns JSON (empty response = routes still not up = boot still failing).

Same-class risk packages: `cpu-features` (known optional-install failure, harmless), `lightningcss` (this incident). After ANY dependency-merge plugin update, if web won't boot, check for missing native modules FIRST — before renaming node_modules.

**Automated since 2026-08-19:** dsh-desktop launch runs `dsh-maintain.js --fix` (main.rs `ensure_dsh_maintenance`, detached — log `D:\All projects\DSH\dsh-maintain.log`). It auto-repairs missing native binaries (downloads the matching-version `.node` from npm), re-applies the color patch, applies incremental plugin updates via the official API, and health-checks web. The manual fix above remains the fallback when web is down or the auto-run did not fire.

## Migration to a New Root

Validated strategy (2026-08): copy **excluding all `node_modules`** (junction trees expand into real dirs on copy and the source link layer may already be broken), then rebuild deps at the destination (`source` + `profiles/web` `pnpm install`). A user-side `robocopy /E` full copy including node_modules stalls on junction loop expansion and fabricates self-referential junctions (cordis → cordis …) — that was the historical "plugin load failed" root cause. Old root stays untouched during/after migration; verify sessions/storages file counts match between roots before claiming zero loss.

## Junction Recovery

Self-referential / looping junctions cannot be removed by `rd`, PowerShell recursive delete, or `fs.rmSync` (they follow symlinks). **Rename instead of delete** (`fs.renameSync`) to park the broken tree; DSH's `healProfilesModuleFallback` rebuilds clean junctions on next boot (verify: junction count matches source, e.g. 195/195). Parked trees (`node_modules.mig-bak*`) are cleanup candidates after confirmation, not before.

## Desktop Shell (dsh-desktop)

- Rebuild: `build-x.ps1` (requires SUBST `X:` → dsh-desktop root + rust GNU toolchain; incremental ~24s).
- Icons / window icon / broken-asset regen / rcedit: see `desktop-build-verification` §7l + `references/tauri-windows-rebuild-and-icons.md` — already covers the cargo TOML escape, windres space-path, tauri 2.11.x `set_icon`, WM_GETICON verification, favicon→PIL icon generation, and the dark-theme contrast rule.
- Color patch (root cause, 2026-08-19): `dsh-update-checker` (`lib/client.js`) uses **`--dsw-alias-brand-primary` as the button background** — that is an *accent* color (near-white under the official dark theme, light-blue `#8ab4de` under whale-song skin) → white-on-light unreadable text. The official button semantics are `--dsw-alias-button-primary-fill` (fill; dark-blue `#2f6fb8` under whale-song) + `--dsw-alias-label-primary-foreground` (contrast text; white under whale-song, black under official dark). Patch both primary rules (`.dsh-update-btn-primary`, `.dsh-plugin-btn-primary`) to use those two vars for background+color. It lives in node_modules → a plugin update (or any pnpm restore) overwrites it; `dsh-maintain.js --fix` re-applies at every desktop launch (background + color replacements must be independent — an early `if (!includes('color:#fff')) return` skips the background upgrade).

## Update Strategy (three layers, validated 2026-08)

DSH has a built-in updater (`dsh-update-checker`) — but it only fully serves the **plugin layer**. Know which layer you are updating:

| Layer | Location | Update path | Who |
|---|---|---|---|
| Plugins | `profiles/web/node_modules` third-party (`@linxin666/*`, `@a9i5k4/*`, `@anionex/*`, `dsh-update-checker`, …) | **DSH UI banner / plugin center** — built-in backup (`.dsh-plugin-backups/`) → install → verify → restart watchdog → rollback route | official, zero-maintenance |
| Core (official `@deepseek-ai/*`) | `source/packages/*` — **resolved from the source workspace, NOT from `profiles/web/node_modules`** | rides along with a core upgrade (source checkout) | manual SOP below |
| Main runtime | `source` (git pin + pnpm workspace) + `dsh-home` data | **manual** — see SOP | Hermes/DSH |
| Desktop shell | `dsh-desktop` (Tauri) | incremental rebuild via `build-x.ps1` (~24s); no change needed when core updates keep URL/port (127.0.0.1:3080) | Hermes |

**Why the built-in updater can't upgrade the main runtime on this deployment:** `status.json` reports `installed: null` / `hasUpdate: false` because it detects local installs via npm (`@deepseek-ai/dsh` global/project), which does not exist for a **source-clone deployment**. Plugin scan (`plugins.json`) DOES work — it walks `profiles/*/node_modules` (pnpm-hoisted aware).

**Plugin architecture fact (corrects "junction count" assumptions):** in a healthy running DSH, `profiles/web/node_modules` top level = pnpm deps + third-party plugins (real dirs). Core `@deepseek-ai/*` is NOT present there (workspace-resolved). So do not treat a missing `@deepseek-ai` in `profiles/web/node_modules` as breakage — treat a **page that renders + web log `ready` lines** as the health signal (see Diagnosis step 4).

**Core upgrade SOP (source-clone):**
1. Backup `dsh-home` first (sessions/storages/profiles config; exclude node_modules) to a dated dir.
2. Stop the web process tree, confirm 3080 free.
3. `git fetch origin` — **needs proxy**: `git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 fetch origin` (direct GitHub fails with connection reset).
4. Checkout the target (keep detached-pin style, e.g. the release merge commit / tag).
5. `pnpm install --frozen-lockfile` in `source/` root.
6. **Do NOT touch `profiles/web/node_modules`** unless the new version demands it (empty-shell red line). If it must change: rename the whole dir, reinstall, and immediately verify.
7. Restart web → verify HTTP 200 + page renders + plugins active (no pending).
8. Re-apply the update-checker color patch if that plugin changed (see Color patch).
9. Rollback: checkout the old pin → `pnpm install --frozen-lockfile` → restore dsh-home backup → restart.

**Color patch durability (fully solved 2026-08-19):** `dsh-update-checker` 1.4.8 (tested) STILL hardcodes `color:#fff` on the primary buttons — the node_modules patch is overwritten by every plugin update. **Why it kept recurring (root cause):** dshmarket/update-checker installs/updates run pnpm, which **restores ALL node_modules files from the lockfile** — API updates change the installed package but NOT the `dependencies` version declaration in `profiles/web/package.json`, so any later pnpm op (e.g. market-installing a new plugin) restores both the old package version AND the patch. **Durable fix (validated):** ① after any API update, manually sync the `package.json` declaration (`dsh-update-checker: ^1.4.3` → `^1.4.8`) so pnpm never restores the old version; ② re-apply the patch (`.hermes/task-runtime/reapply-dsh-color-patch.py`); ③ dsh-maintain.js startup self-heal re-applies it after any restore. The dsh-skins custom-skin route was evaluated and REJECTED as a durability fix — skin assets also live under node_modules (`@linxin666/dsh-skins/skins/`), so pnpm restores overwrite them too. Skins remain a *visual* layer only (apply via `POST /api/skin-center/apply {"skin":"<id>"}`), not a patch-persistence mechanism.

## Handoff-Document Discipline



When writing/updating the DSH handoff docs in a WORK-LAB checkout, re-check git state FIRST — main may have moved (deliverables merged via PR, volume-expansion archiving done) since your last session; never assert "N files uncommitted" without `git status` + `git log`. The handoff must reflect the current main HEAD and what is actually pending.

## Verification Quicklist

- web: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3080/` → 200
- plugins: browser snapshot shows 任务看板/技能中心/session tree; web log has `[dsh-*] ... ready/已注册`
- junction: Node lstat symlink count matches source shared dir
- icon: exe `ExtractAssociatedIcon` quantized-color count > 1 (a 1-color/pure-white image = broken asset); window icon via WM_GETICON, not GetClassLongPtr(GCLP_HICON)
