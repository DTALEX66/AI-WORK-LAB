# WORK-LAB → DSH 更新 SOP（2026-08-19）

> DSH（DeepSeek Harness）**三层更新机制**：插件 / 主体 / 外壳。本文件是持续
> 更新 DSH 的唯一权威操作流程，覆盖备份、更新、验证、回滚与补丁维护。
> 归入 WORK-LAB `50-taskpacks/`，与 `WORK-LAB-DSH-HANDOFF-2026-08-18.md` 配套。

---

## 0. 三层结构与各自的更新方式（TL;DR）

| 层 | 位置 | 更新方式 | 维护方 |
|---|---|---|---|
| **插件** | `dsh-home/profiles/web/node_modules/`（第三方 @linxin666/@a9i5k4/@anionex 等 + 官方核心走 source workspace） | **DSH UI 内建**（dsh-update-checker：备份 → 更新 → 校验 → 重启看门狗 → 回滚） | DSH 官方机制，**零维护** |
| **主体** | `D:\All projects\DSH\deepseek-harness\source`（git pin + pnpm workspace）+ `dsh-home`（数据） | **手动脚本**（官方 update-checker 的 npm 检测对 source 克隆部署无效，`installed=null`）→ 见 §2 | Hermes/DSH 维护 SOP |
| **外壳** | `D:\All projects\DSH\dsh-desktop`（Tauri 壳） | 本地代码修改 + `build-x.ps1` 增量重建 | Hermes 维护 SOP |

> **结论**：插件层"完美方案"= 官方 UI 一键（已内置备份/回滚）；主体层"完美方案"
> = 脚本化更新（带备份/回滚/验证，见 §2）；外壳层 = 增量重建（24s）。

---

## 1. 插件更新（官方机制，UI 一键）

### 1.1 机制（dsh-update-checker，实测 1.4.3 已内置）

- 前端横幅：主程序更新（`/dsh-update-checker/status.json`）+ 插件更新（`/dsh-update-checker/plugins.json`），每 6 小时自动复查。
- 后端路由：`GET plugins.json`（扫描多位置插件，pnpm hoisted 兼容）、`POST install`（备份 → 布局自适应安装 → 回读校验 → 生态同步）、`POST rollback`（按 `.dsh-plugin-backups` 备份回滚）、`POST restart`（两级 spawn 脱钩 + 看门狗重启 web）。
- 备份目录：`DSH_HOME/.dsh-plugin-backups/`。

### 1.2 操作（2026-08-19 快照：28 插件，22 个可更新）

- 浏览器/桌面壳打开 DSH → 顶部横幅"发现新版本，检查更新" → **插件横幅：单个更新 / 全部更新**。
- 可更新（patch/minor）：`@a9i5k4/dsh-auto-memory`(0.1.26→0.1.28)、`@anionex/dsh-vision-toolkit`(0.1.32→0.1.34)、`@linxin666/*` 13 个(0.2.0→0.2.3)、`dsh-better-sidebar`、`dsh-effort-slider`、`dsh-find-plugin`、`dsh-update-checker`(1.4.3→1.4.8)、`dshmarket`、`@liustack/modlens` 等。
- 已最新：`dsh-computer-use`、`dsh-mermaid`、`dsh-monitor`、`dsh-tier-router`、`dsh-vision-tools`、`dsh-voice-input-web` 等。

### 1.3 API 批量更新（实测 2026-08-19，官方机制封装）

```text
接口：POST http://127.0.0.1:3080/dsh-update-checker/plugin-update
Body：{"name":"<插件名>", "confirm": true}     # confirm 必须为 true（writeGate 强制）
约束：loopback 来源（127.0.0.1）方可调用；单飞锁 600s（同一时刻只允许一个更新任务）
脚本：.hermes/task-runtime/update-dsh-plugins.py（读 plugins.json 可更新清单 → 逐个更新，
      dsh-update-checker 自身排最后 → 完成后重打颜色补丁）
实测：每插件约 2-3 分钟（npm 下载 + 临时目录安装 + 拷贝 + 依赖核对），22 个约 40-60 分钟
注意：不要用 plugins.json?fresh=1（强制重扫 npm 慢，脚本 40s 超时曾误报 0 可更新）
```

### 1.4 ⚠️ 更新后的必做项（颜色补丁重打）

**dsh-update-checker 1.4.8 实测仍未修复白字问题**（`.dsh-update-btn-primary` / `.dsh-plugin-btn-primary` 仍硬编码 `color:#fff`）→ **每次更新 dsh-update-checker 后必须重打颜色补丁**：

- **pnpm 还原陷阱**（2026-08-19 实证）：dshmarket 装/卸插件会跑 `pnpm install` → 从 lockfile **还原所有插件到旧版本**（update-checker 1.4.8→1.4.3、颜色补丁消失）。**根治**：批量更新后必须**同步 package.json 依赖声明**到最新版本（`update-dsh-plugins.py` 已内置；`^1.4.3 → ^1.4.8`），pnpm 下次解析到同一版本，不再还原。

```
文件：D:\All projects\DSH\deepseek-harness\dsh-home\profiles\web\node_modules\dsh-update-checker\lib\client.js
两处：color:#fff → color:var(--dsw-alias-label-primary-foreground,#0f1115)
（.dsh-update-btn-primary{...} 与 .dsh-plugin-btn-primary{...} 各一处）
```

（可选更持久方案：利用 dsh-skins 皮肤中心做用户 CSS 覆盖，不碰 node_modules——见 §4。）

---

## 2. 主体更新（脚本化 SOP）

> 官方 update-checker 主程序更新走 npm（`@deepseek-ai/dsh`），对**source 克隆部署**
> 无效（status.json 实测 `installed:null`、`hasUpdate:false`）。主体更新 = 本 SOP。

### 2.1 当前版本基线

- **pin（当前）**：`99f6f02f`（`0.1.0-rc.7`，2026-08-20 升级完成；source 为 partial clone [blob:none]，origin 已改 SSH `git@github.com:deepseek-ai/deepseek-harness.git`——fetch/checkout 直连可用，无需代理）
- **回滚 pin**：`47f94385`（`0.1.0-rc.5`，旧基线，备份 `dsh-backup-2026-08-20/`）
- fetch 需走代理：`git -c http.proxy=http://127.0.0.1:7890 -c https.proxy=http://127.0.0.1:7890 fetch origin`

### 2.2 更新步骤（每步在 Hermes 会话中执行，涉及外部动作先报备）

```text
① 备份（必须）：
   robocopy 复制 D:\All projects\DSH\deepseek-harness\dsh-home
             → .hermes/task-runtime/dsh-backup-<date>/（排除 node_modules）
   （sessions/storages/profiles 配置为关键数据；node_modules 由 install 重建）

② 停 web：kill 3080 进程树（netstat -ano | grep :3080 → 父进程链）

③ git 更新（source，cwd = source）：
   git fetch origin（代理 7890）
   git checkout 99f6f02f（或 0.1.0-rc.7 目标 commit；保持 detached pin 风格）
   git -c http.proxy=... fetch origin 后再 checkout 新 commit

④ 重建依赖（source 根）：
   pnpm install --frozen-lockfile（node 经 Hermes node 目录 + corepack pnpm@11.7.0）

⑤ ⚠️ profiles/web/node_modules：禁止手动 pnpm install（防空壳红线，见 §5）。
   若新版确实要求 web 依赖变更，备份后整体 rename 再 pnpm install，并立即验证。

⑥ 启动 + 验证：
   python .hermes/task-runtime/start-dsh-dest.py   # HTTP 200 检查
   浏览器 http://127.0.0.1:3080 → 插件全激活（无 pending）+ 会话树完整
   curl http://127.0.0.1:3080/dsh-update-checker/plugins.json → 插件清单正常

⑦ 颜色补丁重打（如 dsh-update-checker 随更新变化）：§1.3
```

### 2.3 回滚（更新失败/插件 pending）

```text
① 停 web
② git checkout 47f94385（旧 pin）→ pnpm install --frozen-lockfile
③ 恢复备份：robocopy 回拷 dsh-home（数据文件覆盖，node_modules 由 install 重建）
④ 启动 web → 验证
```

---

## 3. 外壳更新（dsh-desktop）

### 3.1 当前壳

- Tauri 2（tauri 2.11.5）壳：加载 `http://127.0.0.1:3080` + 内置 `ensure_dsh_service`（3080 未起则 `node run-dsh.js ... web` 自动拉起）。
- 图标（exe/窗口/任务栏/快捷方式/setup）= 品牌蓝 + 白鲸鱼（`src-tauri/icons/` 全套 + `lib.rs` `setup` 里 `WebviewWindow::set_icon`）。
- 构建环境：SUBST `X:` → `D:\All projects\DSH\dsh-desktop`（重启后需重建）+ rust GNU toolchain（`stable-x86_64-pc-windows-gnu`，rsproxy）+ `~/.cargo/config.toml`（已修转义，勿再写未转义反斜杠）。

### 3.2 更新流程

```text
① 改代码：src-tauri/src/lib.rs（壳逻辑/窗口图标）、src-tauri/tauri.conf.json（窗口/打包）
② 增量重建：powershell -File "D:\All projects\DSH\dsh-desktop\build-x.ps1"（~24s 增量）
   （build-x.ps1 已设 CARGO_TARGET_DIR=X:\src-tauri\target 无空格路径）
③ 产物自动落位：X:\src-tauri\target\release\dsh-desktop.exe + bundle\nsis\setup.exe
④ 重启桌面壳验证（窗口图标 = WM_GETICON 512×512/7 色鲸鱼）
```

### 3.3 主体更新对外壳的影响

- URL/端口不变（127.0.0.1:3080）→ **主体更新后外壳一般无需变动**。
- 若新版 DSH 改变 web 端口/启动参数 → 同步改 `lib.rs` 的 `ensure_dsh_service` 参数 + 重建。

---

## 4. 颜色补丁的持久方案（可选升级）

- **现状**：node_modules 补丁（§1.3），插件更新会覆盖，需重打。
- **更持久**：dsh-skins 皮肤中心（`profiles/web/node_modules/@linxin666/dsh-skins/`）——皮肤 = CSS 注入。若皮肤支持用户自定义 CSS，可做**自定义皮肤**覆盖按钮文字色（`--dsw-alias-label-primary-foreground`），**不碰 node_modules**，插件/主体更新永不丢失。
- **待办**：验证 dsh-skins 自定义皮肤入口（skin.json 格式）后实施。

---

## 5. 防空壳红线（不可违反）

1. **`profiles/web/node_modules` 禁止手动 pnpm install / npm install**——hoisted 重装会把 workspace 插件链接打成空壳（2026-08-19 事故根因：149 空目录 → 45 插件 pending）。
2. 插件安装/更新一律走 **DSH UI 插件中心/更新横幅**（官方机制，自动备份回滚）。
3. 任何依赖重装后**必须**验证：浏览器插件全激活（无 pending）+ `plugins.json` 扫描正常。
4. 空壳事故处置（已实测有效）：停 web → `rename profiles/web/node_modules → .mig-bak<N>` → `pnpm install`（web 目录，用 `.hermes/task-runtime/install-dsh-dest.py`）→ 重启 web → 验证。

### 5.1 ⚠️ 插件更新后依赖二进制缺失（2026-08-19 实测事故）

**症状**：批量插件更新后重启 web 失败，日志：`Cannot find module '../lightningcss.win32-x64-msvc.node'`（或同类原生模块）。

**根因**：update-checker 更新插件时升级了共享依赖（如 lightningcss 1.32.0→1.33.0），但**可选依赖二进制包**（`lightningcss-win32-x64-msvc`）未随装 → `.node` 缺失 → web boot 崩溃。

**处置（不动布局/lockfile）**：
```text
① 确认缺失模块：读 <包>/node/index.js 的 require 路径
② 从 npm registry 下载对应版本二进制 tarball：
   curl https://registry.npmjs.org/<binary-pkg>/<version> → dist.tarball
③ 解压 .node → 放置到 profiles/web/node_modules/<pkg>/<要求的文件名>
   （Python tarfile 解包，绕过 install；不碰 lockfile/布局）
④ 重启 web（start-dsh-dest.py）→ 验证 HTTP 200 + plugins.json
```

**同类风险包**：cpu-features、lightningcss 等原生模块（安装时常见 optional dep 失败）。

---

---

## 6. 网络提速与安全（2026-08-20 实测）

### 6.1 为什么插件更新慢（根因 + 修复）

- **根因**：npm registry 直连被限速 **~133KB/s**（每包 4s+ → 31 插件数分钟）。
- **修复**：`profiles/web/.npmrc` 切 **npmmirror**（`registry=https://registry.npmmirror.com`）→ **快 11 倍**（1.5MB/s）——批量更新从 10+ 分钟降到 ~50s。
- **注意**：.npmrc 不要配 `proxy=7890`（会拖慢 npmmirror；代理只给 github 走 env `HTTPS_PROXY`，见下）。

### 6.2 github 连接（SSH 优先，代理兜底）

- **SSH 直连**（最快最稳）：用户已有 `id_ed25519` 挂在 github（实测 `Hi DTALEX66!`）；22/443 端口通；已配
  `git config --global url."git@github.com:".insteadOf "https://github.com/"`（pnpm 的 github 依赖也走 SSH）。
- **代理下载**（7890）：curl `-x http://127.0.0.1:7890` 对 codeload/github 有效（2.4s）；用户另有 VPN（FlClash）可兜底。
- **market install 的 fetch 走 7890 会失败**（undici CONNECT 被 CC Switch 拒）→ **新插件用 SSH clone 手动装**（见 §6.4）。
- **cloudflared 下载**（remote-web-ui/web-ui-all 的依赖）卡 github releases → web 启动 env 设 `HTTPS_PROXY=7890`（start-dsh-dest.py 已加）。

### 6.3 装前审计（用户要求，强制）

新插件（尤其 github 源）装前必须：
1. `package.json`：依赖/peerDeps/scripts（postinstall 等恶意命令检查）
2. 源码扫描：`child_process` / `process.env.KEY` / `fetch(` 外连 / `writeFileSync` / `eval(`——命中看上下文（three.js 等 vendor 库正常）
3. peerDependencies vs 主体 rc 版本（**rc 不匹配 = 软不兼容风险**：obsidian-memory 崩（config undefined）、genui rc.8 缓装）
4. apply 的 `config` 访问防护（`config = {}`——防 cordis rc.5 传 undefined 崩）

### 6.4 手动安装新插件（绕 market fetch 失败）

```sh
# 1. SSH clone
git clone --depth 1 git@github.com:<owner>/<repo>.git  # 到 .hermes/task-runtime/
# 2. 审计（§6.3）
# 3. 放置（scoped 包 → node_modules/@scope/name；bundle 名必须带 scope 匹配包名！）
# 4. package.json：dependencies[name]=version + dsh.profile.bundles 加 name
# 5. 重启 web（start-dsh-dest.py）→ 验证 plugins.json 加载 + 无崩溃 + 页面功能
```

**bundle 名坑**：scoped 包（`@dsh-external/xxx`）的 bundle 注册必须带 scope，否则 `resolveBundleDir` 报
`cannot resolve profile bundle`。

### 6.5 新增 UI 插件清单（2026-08-20）

- `@dsh-external/dsh-client-ui-skin-maid-atelier` 0.0.1：深海女仆工坊皮肤（已装，生效，标题"深海女仆工坊"）
- `open-sea-skin` 1.2.1：WebGPU 海洋皮肤（已装，`/open-sea-skin` 路由 + iframe + "海洋皮肤设置"按钮）
- `@dsh-external/dsh-visualize` 0.1.2：对话内生成式 UI（已装，rc.6 peers + config 防护补丁；**genui 替代**——genui peer 全 rc.8 缓装）
- 未装：dsh-TUI（终端 UI 独立客户端，可另议）、deepseek-design（rc.5 未测）、modlens 3.22（cloudflared 卡，3.21.1 可用）

---

## 7. 相关脚本与文件（.hermes/task-runtime/）

| 文件 | 用途 |
|---|---|
| `start-dsh-dest.py` | 启动新位置 web（HTTP 200 验证） |
| `install-dsh-dest.py` | 重建 source + profiles/web 依赖（pnpm） |
| `run-pnpm.js` / `run-dsh.js` | pnpm 逐次 pin / dsh CLI 包装 |
| `gen-dsh-icons.py` | 品牌图标生成（favicon.svg → 全套） |
| `run-build-x.py` / `build-x.ps1` | dsh-desktop 构建（SUBST X:） |
| `verify-dsh-dest.py` / `fix-dsh-dest.py` | 迁移验证 / 循环 junction 绕行 |

---

*更新 SOP 生效。任何更新动作前先备份，更新后先验证插件加载，失败即回滚。*

---

## 8. 调研结论落地（2026-08-20 三路调研）

### 8.1 node-pty 崩溃（根治：PR #886 补丁 + maintain 自动兜底）
- **根因**（microsoft/node-pty#952）：1.1.0 kill() 竞态——agent fork 完成时 shell 已退出 → `AttachConsole(死pid)` 失败 → agent 无 try/catch 直接崩（无控制台进程实测 14/15 崩溃）。
- **修复**（PR #886 已合入 v1.2.0-beta.11+）：agent try/catch 返回空列表 + `windowsPtyAgent._innerPid<=0` 直接 resolve。**本机已打补丁**（lib/ 两个文件）+ **maintain `nodePtyFix()` 自动重打**（防 pnpm 还原）。
- **升级替代**：node-pty 升 1.2.0-beta.11+（官方修复内置）——下次 better-sidebar 更新时可试。

### 8.2 补丁被还原的真正机制（pnpm 硬链接）
- **根因**（pnpm/pnpm#753，zkochan 本人）：node_modules 与内容寻址 store 是**硬链接**——直接改 node_modules = 改 store → pnpm 校验 hash 不符 → 从 registry 重新下载还原。
- **官方方案**：`pnpm patch <pkg>` + `pnpm patch-commit` → `patchedDependencies`（v11 写 `pnpm-workspace.yaml`，package.json 的 `pnpm` 字段已弃用）；patch-package 在 pnpm 上冗余。
- **当前策略**：maintain 启动自动重打（颜色/obsidian/node-pty 三个补丁）——已够用；**后续可迁移到 pnpm patch 机制根治**（待主体 rc.7 升级后一并做）。

### 8.3 更新机制官方最佳实践（update-checker README = 事实标准）
- 更新后**必须把新版本写回 profile package.json + 同步 lockfile**（`pnpm install --lockfile-only`）——否则 pnpm install 还原旧版 → 反复提示更新死循环。**本机 update-dsh-plugins.py 的声明同步 = 该实践**（补 lockfile-only 为可选增强）。
- 串行队列批量更新；备份在 `$DSH_HOME/dsh-update-checker-backups/`；写路由强制 `{confirm:true}`。
- DSH 官方（deepseek-ai/deepseek-harness）issues 禁用、无插件更新文档——社区插件（Airmetro/dsh-update-checker、dsh-market/dsh-market）是权威。

---

## 9. 0.1.1-rc.2 升级失败结论 + rc.7 恢复（2026-08-21）

### 0.1.1-rc.2 不可用（2 天前新 minor）
- 现象：单插件也死锁（0 输出 CPU 0.8）；duplicate loader entry（dsh-market/modlens）逐层清后仍卡
- 根因：dshmarket 生态插件（cordis.patch.yml 每插件 insert dsh-market + bundle 声明）与 0.1.1 的 cordis 4.0.1 不兼容；0.1.1 需要 pnpm build（源码链接无 lib）+ 官方插件生态未适配
- 结论：0.1.1 等 rc.3+/稳定版 + 插件生态适配后再迁（预计 1-2 周）

### rc.7 恢复路径（已验证）
- source: rc2-tarball/worktree-rc7-bak → update-ref HEAD 99f6f02f → pnpm install
- web profile: web-profile-bak → 删 pnpm-lock.yaml → github: 引用改 npm 版本（npm view 逐个）→ pnpm install
- obsidian-memory: vaultPath 默认值补丁（config = { vaultPath: "E:\\BaiduSyncdisk\\Obsidian知识库" }）
- 插件 cordis.patch.yml 统一置空（0.1.1 留下）——rc.7 无碍
- 凭据文件被 0.1.1 迁移（version+refs）→ 从 rc7 备份恢复（8/20 后新填凭据需重填）

### 网络通道（本轮强化）
- gh CLI（scoop，已认证 DTALEX66）→ GitHub release 资产下载（Obsidian 315MB/codex rust 283MB）——认证 5000/h 不限速
- git SSH（origin 直设 git@github.com:）——fetch/checkout；全局 insteadOf 的坏引号 section 已删
- npm → npmmirror（web .npmrc + pnpm 源）
- 7890 代理：curl/git https 大文件

### 其他软件更新（2026-08-21）
- Codex 0.149.0（npm 包装 + gh 下载 rust 283MB 替换 vendor codex.exe——npmmirror 无 win32-x64 0.149）
- Obsidian 1.13.7（gh 下载 315MB 静默装 D:\Programs\Obsidian；1.13.8 只是安卓包）
- Open Design 0.20.1（launcher 自更待确认）；Hermes 0.20.5 待升（remote 引号修）


## 10. 0.1.1-rc.2 正确升级路径（2026-08-22 验证）
- ❌ **tarball 源码手动装 = 死锁**：源码缺 lib（需 build），build 后 cordis 与 dshmarket 生态插件不匹配 → 单插件 init 死锁（CPU 0.8 挂起、0 输出）。
- ✅ **DSH 官方 runtime 自更新**（commit 4446888 "DSH Official Runtime"）：预构建 lib/dist，cordis 打包正确 → **17 插件全 latest 匹配、无死锁、web healthy**。
- 结论：0.1.1 升级**只走官方 runtime 自更新**，绝不用 tarball/codeload 源码覆盖。

## §11 GH_TOKEN 与更新检查（2026-08-22）

- 403 根因链：`setx GH_TOKEN` 只写用户环境 → **已在运行的 web 进程（孤儿/dsh-desktop 旧快照）读不到** → update-checker 空 token → rate limited。
- 修复：杀 3080 旧进程 → 用 `start-dsh-dest.py` 重启（内置 winreg 读 GH_TOKEN 注入 env）。
- update-checker 多副本（web/node_modules + profiles/node_modules + backups/）为自更新正常机制，勿删；判断加载副本看 ghError/status 而非目录。
- 插件审计方法：实际有用性 + 与既有工具重复（如 dsh-computer-use↔Hermes）+ 市场质量（星/下载）；审计后 17 插件保留全绿。
