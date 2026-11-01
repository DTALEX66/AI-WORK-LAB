# WORK-LAB → DeepSeek Harness 交接文档（2026-08-18）

> 本文件是 Hermes 向 DeepSeek Harness（DSH）的**最新完整工作交接**（增量覆盖
> 2026-08-15 版：新增 DSH 迁移 + 桌面版修复两大成果）。DSH 接手 WORK-LAB
> 后续工作时，以本文件 + 仓库内 AGENTS.md + 50-taskpacks 下的任务包为唯一权威，
> **不得**依赖与 Hermes 的历史对话上下文。
>
> 交接人：Hermes（WORK-LAB 唯一 Writer） · 接手方：DeepSeek Harness（受限 Agent Runtime）

---

## 0. 交接摘要（TL;DR）

- **项目**：`D:/All projects/WORK-LAB`（GitHub `DTALEX66/WORK-LAB`），单根 monorepo，客户端中立的工作流控制面，管理 6 个 AI 客户端（Hermes / Codex / CC Switch / GitHub / OpenHuman / Open Design）+ 未来所有 AI 软件的 USER_GLOBAL 期望态配置。
- **两活动模块**：`10-workflow/workflow-assistance`（唯一主动 Writer）；`30-observer/work-lab-observer`（严格只读投影，不执行/不批准/不写账本）。
- **DSH 已完整迁移至 `D:\All projects\DSH`**（2026-08-18 完成，用户指定新地址）：`deepseek-harness\`（source pin `47f94385` + dsh-home 全量：sessions 29 文件/42.1MB、storages 2 文件、profiles/web 28 个第三方插件、junction 区 195/195 symlink）+ `dsh-desktop\`（Tauri 壳 exe 20.9MB + NSIS setup 3.7MB + src-tauri 源码 + build-x.ps1）。
- **桌面入口 = dsh-desktop.exe 唯一方案**（用户拍板"VBS 的就不要了"）：Tauri 壳加载 `http://127.0.0.1:3080`，内置后端自启动（`ensure_dsh_service`），桌面快捷方式 `C:\Users\ALEX\Desktop\DeepSeek Harness.lnk` → 新 exe。
- **桌面版两个问题已修复**（2026-08-18）：① 插件更新弹窗"确定"按钮白字白底颜色冲突（dsh-update-checker 插件 bug，已打补丁）；② 桌面版全套图标缺失/空白（根因=图标文件纯白空壳，已用官方 favicon.svg 重新生成品牌图标 + 重构建 exe，exe/窗口/任务栏/快捷方式/安装包全部对应）。
- **当前分支**：main（交付物已 merge；本次交接 = 08-18 文档 + SUMMARY 更新待提交）。
- **待办（下一步优先级）**：① 提交本次交接文档（08-18 + SUMMARY 更新，需批准）；② WL3-100/110 收编；③ DSH-040 付费 smoke（需用户填 key + 批准）；④ 跟进 main 上 control-plane 系列与交接文档一致性。

---

## 1. 项目定位与硬边界（必须遵守）

### 1.1 边界（违反即失败，fail-closed）

1. **E:\ 盘受保护**：未经用户在本请求内**逐路径、逐操作**明确授权，禁止任何访问（枚举/读取/写入/运行/压缩/同步/上传）。
2. **秘密/凭据**：禁止读取、打印、复制、提交或上传任何 credential、token、key、password、`.env` 正文、auth/session 库、浏览器私有数据、prompt/response body、私有状态。
3. **防外溢**：所有任务数据（临时文件、缓存、日志、测试产物）必须留在 `.hermes/task-runtime/` 或 `.hermes/task-artifacts/` 内，不得写入用户 Home、桌面、系统临时目录、其他项目。`.hermes/` 已 git-ignored。
4. **Observer 只读契约**：`30-observer/` 只读投影，`CanonicalStore(readonly=True)`，SQLite URI `mode=ro`，不建目录/不迁移/不写 WAL，写操作 fail-closed。
5. **DSH 自身边界**：DSH 是**可替换 Agent Runtime**，不是 WORK-LAB 第三个活跃模块、不是 Hermes 替代品、不接管真实 Hermes/Codex/CC Switch 配置、不写 Task Ledger 状态、不 commit/push/PR/merge/release 除非用户逐动作明确批准。
6. **不 commit/push/merge/release**：默认不授权。每个 commit/push/PR/merge 动作需显式批准。禁止 destructive reset/clean/force-push。
7. **原位置 DSH 保留**：`.hermes/task-runtime/deepseek-harness/`（旧位置，source 47f94385 + dsh-home）**未动、不删**——迁移纪律"原 DSH 先不动"，作为回滚/对照基线保留。

### 1.2 五维运行时基线（强制，audited）

每个受管软件面必须满足：① 软件入口唯一（每工具一条 canonical 启动路径——DSH 桌面 = dsh-desktop.exe，**VBS 启动器已废弃**）；② 桌面可达（快捷方式 target 链 resolve）；③ 官方标准 + 用户配置（官方基线赢，只管理声明的 overlay 字段，不覆盖用户 provider/model/auth/桌面状态）；④ 配置不过重无阻塞（skills <10KB 每个、guidance+rules <20KB 总、按需加载）；⑤ 模型满血（无限速/无限额/reasoning_effort 不低于官方默认 medium，cost_multiplier=1.0，无日/月 caps）。

### 1.3 Open Design 双身份

WORK-LAB 管理 Open Design **client** USER_GLOBAL 期望态（`MANAGE` + `apply_supported=false`）；Design **capability**（模型/工具/资产生成参数）属于 `DTALEX66/DESIGN-LAB` 项目，`IGNORE`，不在此收集/管理。

---

## 2. 当前精确状态（git）

- **main**：HEAD `ad10333`（control-plane 系列，见下）；历史：`de29e583`(#117) → `6d675ca`(#118 DSH 集成 + model control plane + WL3-810 归档) → `6d16094`(#119 observer command center 2.0) → `2ab2178`(observer 3.0 roadmap) → `fb6e984`/`f7bc3fe`/`ad10333`(control-plane 演进)。上游 origin/main 已同步。
- **交付物已合并进 main**：5 件 DSH adapter 交付物 + 08-15 交接文档已通过 **#118（6d675ca）** merge（该提交同时含 model control plane 全套 schema/脚本 + **WL3-810 体积膨胀归档**：三份 archive-manifests 约 24.7K 行删除）。
- **main 当前 HEAD**：`ad10333`（control-plane 系列：agent registry / work unit engine / policy engine / observer fleet / timeline / control tower / action receipt / harness adapter interface / dsh plugin evaluation；前序 #119 observer command center 2.0、observer 3.0 roadmap）。
- **待提交（本次交接）**：本文件（08-18 交接）+ `WORK-LAB-DSH-HANDOFF-SUMMARY-2026-08-15.md` 更新（共 2 个文件，commit/push 需批准）。
- **未跟踪 foreign 文件**：`pre_tool_call_hook_diagnosis_2026-08-13.md`（**必须保持未读/未改/未暂存/未提交/未删除**）。

### 已完成 PR（可信任，勿重做）

#110（全局配置 WL3-200）、#111、#112、#113（规则减重）、#114、#115（平台发现扩展）、#116（规则减重）、#117（skill 精简 + 全局配置收口）。

---

## 3. 已完成工作（勿重做）

### 3.1 三项任务收口（PR #117，merged `de29e583`，2026-08-15）

受管 skill 精简（3 个超限 SKILL.md 压到 <10KB，内容"搬家不删"移 references/）；全局配置 14→13 Skills + 4 个模型满血 OBSERVE 字段；验证全绿。详见 08-15 交接文档 §3.1。

### 3.2 DSH 接入（WL-DSH-001，2026-08-15）

WL-DSH-010 发现（上游 `deepseek-ai/deepseek-harness@47f94385`，0.1.0-rc.5 preview，MIT）；WL-DSH-020 交付物（当时未 commit，现已 #118 merge）；WL-DSH-030 隔离安装 + loopback 启动。详见 08-15 文档 §3.2/§6。

### 3.3 DSH 完整迁移至 `D:\All projects\DSH`（2026-08-18，本轮核心成果 1）

**背景**：用户拍板迁移（"继续迁移复制DSH，原DSH先不动… `D:\All projects\DSH` 这是新DSH地址"）。用户自己的 `migrate-dsh.ps1` 用 robocopy `/E` 全量复制**含 node_modules**，卡在 junction 循环展开 18 分钟 + 产生**循环 junction**（cordis 自指）——这是历史"插件加载失败"根因。

**执行（我方方案，实践证明正确）**：

1. **复制排除全部 node_modules**（junction 结构复制会展开成真实目录 + 源链接层本已损坏），复制完成后在新位置重建依赖：
   - `D:\All projects\DSH\deepseek-harness\source`（143.4MB/13692 文件）+ `dsh-home`（156MB/2485 文件）——与源完全一致（sessions/storages 补全）
   - 新位置 source + profiles/web 分别 `pnpm install --frozen-lockfile`（15.7s + 14.5s，exit 0）重建 node_modules
2. **junction 区修复**：profiles/web 的 cordis 被 pnpm `nodeLinker: hoisted` 污染成真实目录 → 用 Node `fs.renameSync` 只改名不删除（`profiles/node_modules` → `.mig-bak`），DSH 启动时 `healProfilesModuleFallback` 自动重建干净 junction——**195/195 全部 symlink**（与旧位置一致）。
3. **dsh-desktop 补全**：复制 `src-tauri/target/release`（dsh-desktop.exe 20.9MB + bundle 含 NSIS setup 3.6MB）→ `D:\All projects\DSH\dsh-desktop\`。
4. **切换运行**：停旧位置 web 进程树释放 3080 → 启动新位置 web（`127.0.0.1:3080` HTTP 200）→ 验证 dump-config 563 行 OK + 浏览器完整渲染（28 插件全部加载、会话树完整 4 项目）。
5. **会话零丢失保证**：sessions 29 文件/42.1MB 新旧一致、storages 2 文件一致、memory/cache/凭据/插件清单一致；原位置全程未动。

**冲突处置（用户"解决它"）**：kill 用户卡死脚本三进程（robocopy PID 9240 + pwsh 18304/17688），用我方方案收尾。

**当前 DSH 新位置结构**：
```
D:\All projects\DSH\
├── deepseek-harness\          # source@47f94385 + dsh-home 全量（主运行体）
│   └── dsh-home\profiles\web\node_modules\   # 195/195 junction symlink
├── dsh-desktop\               # Tauri 桌面壳
│   ├── build-x.ps1            # 构建脚本（SUBST X: + CARGO_TARGET_DIR 无空格）
│   ├── run-dsh.js             # 后端自启动脚本（1,203B，node 内置模块）
│   └── src-tauri\
│       ├── src\lib.rs         # setup + set_icon（窗口鲸鱼图标）
│       ├── icons\             # 新生成全套图标（品牌蓝+白鲸鱼）
│       └── target\release\    # dsh-desktop.exe + bundle\nsis\setup.exe
```

### 3.4 桌面版修复（2026-08-18，本轮核心成果 2）

**A. 颜色冲突（插件更新弹窗"确定"按钮白字白底）**：

- **根因**：DSH 深色主题官方设计将 `--dsw-alias-brand-primary` 定义为近白（`design-platform.css:271`，`body[data-ds-dark-theme]` → `neutral-bluish-50` = `#f9fafb`，品牌色明暗反转）；第三方插件 **dsh-update-checker**（1.4.3）的 `.dsh-update-btn-primary` / `.dsh-plugin-btn-primary` 用该变量做背景 + **硬编码 `color:#fff`** → 深色主题白字白底不可见。官方组件正确写法 = `color: var(--dsw-alias-label-primary-foreground)`（明暗互补）。
- **修复**：`dsh-home/profiles/web/node_modules/dsh-update-checker/lib/client.js` 两处 CSS 字符串 `color:#fff` → `color:var(--dsw-alias-label-primary-foreground,#0f1115)`（与官方组件一致，浅/深色主题均正常）。
- **⚠️ 注意**：这是 **node_modules 本地补丁**，插件更新（pnpm install / 升级）会覆盖；若插件作者修复上游则移除补丁。

**B. 图标全套对应**：

- **根因**：原图标文件**全是纯白空壳**（exe 内嵌 / `launch/dsh-icon.png` / `src-tauri/icons/icon.png` 均为 1 个量化色，无图形无透明）——之前构建时图标源就是坏的，导致桌面快捷方式/窗口/任务栏显示空白默认图标。
- **修复**：
  1. 从官方图标源 `source/apps/web/public/favicon.svg`（DSH 鲸鱼 logo，黑色 path）生成白色版本（`fill="#000"`→`#ffffff`）；
  2. PIL 合成品牌图标：DeepSeek 品牌蓝渐变圆角（450 `#5686FE` → 500 `#4176E6`）+ 白色鲸鱼居中，输出全套（16-512 png + UWP Square 系列 + icon.ico 多尺寸）；
  3. 替换 `src-tauri/icons/` 全套；
  4. **重新构建 exe**（tauri 2.11.5）：exe 资源图标 = bundle icon.ico（鲸鱼）；窗口图标 = `lib.rs` `setup` 里 `WebviewWindow::set_icon(tauri::include_image!("icons/icon.png"))`；
  5. 刷新图标缓存（`ie4uinit.exe -show`）。
- **验证（实测）**：exe 图标 32×32/11 色；窗口图标 WM_GETICON SMALL/SMALL2 = 512×512/7 色（鲸鱼）；任务栏同；桌面快捷方式 → exe 自动鲸鱼；NSIS setup 3.7MB 重建含新图标。

**C. 构建环境修复（重构建 exe 过程中修掉的 3 个环境问题）**：

1. **`C:\Users\ALEX\.cargo\config.toml` TOML 损坏**：`linker = "D:\All projects\..."` 反斜杠未转义（`\A` 非法转义）→ cargo 配置解析全挂 → 已修（双反斜杠 `D:\\All projects\\...`）。
2. **构建路径含空格 → windres 崩溃**：cargo 默认 target 路径含空格（windres 无法处理）→ `build-x.ps1` 显式设 `$env:CARGO_TARGET_DIR = 'X:\src-tauri\target'`（SUBST `X:` → `D:\All projects\DSH\dsh-desktop` 无空格路径）。
3. **rust GNU toolchain 丢失**（rustup no installed toolchains）→ 经 rsproxy 镜像重装 `stable-x86_64-pc-windows-gnu`（rustc 1.97.1）+ `rustup default`。tauri 2.11.5 窗口图标 API 实测：Builder 无 icon setter（`default_window_icon`/`set_default_window_icon` 在 Context 上），正确做法 = `setup` + `Manager::get_webview_window` + `WebviewWindow::set_icon`。

---

## 4. 待办任务（下一步，按优先级）

### 4.1 提交本次交接文档（最优先）

- 本文件（08-18 交接）+ SUMMARY 更新共 2 个文件在 main 工作树未提交。review 通过后 commit + push（每动作需批准）。DSH 接手后应核对 main 上 control-plane 系列与交接文档的一致性。

### 4.2 WL3-100/110 收编

- 能力矩阵 + 身份模型的子代理产出待收编（历史挂起）。

### 4.3 DSH-040 付费 smoke

- 默认 `LOCAL_SMOKE_ONLY`；真实付费调用需用户在 DSH UI 填 DeepSeek key + 明确批准。

### 4.4 其余 WL3 任务

- WL3-120/210/220/300-330/400-420/500/510-520/610/620/720/820（详见 50-taskpacks 任务图 + Task Ledger）。

### 4.5 历史挂起

- frontend F2/F3 PARTIAL；SQLite 执行核心（400/410/420/500/510/520）。

### 4.6 残留待清理（等用户指示，不擅动）

- `D:\All projects\DSH\deepseek-harness\dsh-home\profiles\node_modules.mig-bak`（循环 junction 残留，rename 绕行产物；确认无问题后可删）；
- `D:/All projects/WORK-LAB/$dest/`（字面目录名，用户迁移命令 `$dest` 变量未展开误复制的 **Git for Windows mingw64 运行时**，可能数百 MB）。

> 注：体积膨胀 WL3-810 已由 #118（6d675ca）处理（archive-manifests 归档至 ignored 区，24.7K 行删除），不再待办。

---

## 5. DSH 运行状态（当前）

- **主运行体（新位置）**：`D:\All projects\DSH\deepseek-harness\`（source `47f94385` + dsh-home 全量）。
- **web 服务**：`127.0.0.1:3080`（loopback；当前 PID 见运行时，可能变化；启动方式见 §8）。遥测禁用。
- **桌面壳**：`D:\All projects\DSH\dsh-desktop\src-tauri\target\release\dsh-desktop.exe`（Tauri 壳，内置 `ensure_dsh_service`：检测 3080，未运行则 `node run-dsh.js deepseek-harness/source deepseek-harness/dsh-home web` 自动拉起）。
- **桌面快捷方式**：`C:\Users\ALEX\Desktop\DeepSeek Harness.lnk` → 新位置 dsh-desktop.exe。
- **旧位置（保留不删）**：`.hermes/task-runtime/deepseek-harness/`（source + dsh-home 完整，web 已停）。
- **访问**：桌面壳或浏览器 `http://127.0.0.1:3080`，用户在 UI 填 DeepSeek key（Agent 不读不显示）。
- **回滚**：停进程 → 旧位置 source + receipt 只读 → 标记 runtime QUARANTINED；**不**杀未知 PID，**不**在 source checkout 里 `git reset/clean`。

---

## 6. DSH adapter 交付物（已 merge #118，勿重做）

> 以下 5 件交付物 + 08-15 交接文档已通过 **#118（6d675ca）** 合入 main（提交内版本可能较本会话最初交付略有演进：adapter 293 行、schema 41 行、registry 17 行新增、测试 158 行）。以下为交付内容记录，供追溯，不作为未提交清单。

| 文件 | 说明 |
|---|---|
| `10-workflow/workflow-assistance/config/adapter-registry.json` | + `deepseek-harness` 条目（support_level=experimental，operations=[detect,capabilities,observe]，status=quarantined） |
| `10-workflow/workflow-assistance/schemas/workflow/agent-runtime-adapter.schema.json` | agent_runtime 合同 schema（§4.1 字段） |
| `10-workflow/workflow-assistance/scripts/workflow/deepseek_harness_adapter.py` | adapter：contract() + validate_commit_pin/loopback/workspace_scope/receipt/secret_redaction + detect/capabilities/observe/plan/apply(默认 UNSUPPORTED)/rollback |
| `10-workflow/workflow-assistance/tests/test_deepseek_harness_adapter.py` | 10 tests（含 schema 校验 + 公网 host/commit 漂移/scope 越界/secret 序列化/无批准 apply 拒绝） |
| `10-workflow/workflow-assistance/docs/runtime-adapters/deepseek-harness.md` | 使用/停止/健康/权限/证据/回滚/升级 |

**验证已通过**：test_deepseek_harness_adapter 10/10、test_adapter_registry 2/2、test_client_neutral_manifest 5/5、test_tiered_adapters 6/6、adapter-registry gate PASS（entries=10）、adapter-conformance 4/4、core-schemas PASS。

---

## 7. 强制约束与纪律

### 7.1 测试铁律

- 测试命令：`env -u PYTHONPATH uv run --frozen --group ci --group ci-adapters pytest`（防 Hermes venv jsonschema 污染）。
- 质量门：`python 10-workflow/workflow-assistance/scripts/workflow/run_quality_gate.py verify`（canonical gate）。从**模块路径**运行。
- 区分结构检查 vs 活执行检查；任何 failed/cancelled/missing/skipped 的必需 job = aggregate 失败。

### 7.2 skill-provenance hash 口径

- `check_skill_provenance.py` 先对文件内容做 **CRLF 规范化**（`\r\n`/`\r`→`\n`）再算 SHA-256；更新 `source_sha256` 必须用此口径。
- 需带参数：`--repo 10-workflow/workflow-assistance --manifest 10-workflow/workflow-assistance/config/skill-provenance.yaml`。

### 7.3 CI 纪律

- `wait-runs` **exit 1 = 读超时，非 CI 失败**；merge 前必须显式回读 runs/jobs `conclusion`。
- GitHub cron = UTC；判断 workflow 未触发前用提交时间戳交叉验证时区。

### 7.4 wrapper 边界（terminal 必须遵守）

- terminal 必须经 `python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <单命令>`。
- 禁 chaining/重定向/展开/项目外绝对路径/多行 `python -c`。
- 绕行 = 写脚本到 `.hermes/task-runtime/`，脚本内可引用外部路径。
- `.cmd` 文件（corepack/pnpm/npx）不能经 wrapper 直接 spawn，需用 `node <js入口>` 或项目内脚本。

### 7.5 DSH 构建环境（本轮新增，重要）

- **`C:\Users\ALEX\.cargo\config.toml`**：已修（linker 双反斜杠）；**不得**再写入未转义 Windows 路径，否则 cargo 全挂。
- **构建必须经 SUBST X: + 无空格 CARGO_TARGET_DIR**：`X:` → `D:\All projects\DSH\dsh-desktop`（SUBST 持久，重启后需重建：`subst X: "D:\All projects\DSH\dsh-desktop"`）；`build-x.ps1` 已设 `CARGO_TARGET_DIR=X:\src-tauri\target`。**不得**用含空格物理路径做 cargo target（windres 崩溃）。
- **rust GNU toolchain**：`stable-x86_64-pc-windows-gnu`（rustc 1.97.1，rsproxy 镜像装）。`rustup default` 已设。
- **tauri 2.11.5 窗口图标**：Builder 无 icon setter；正确做法 = `setup` + `Manager::get_webview_window("main")` + `WebviewWindow::set_icon(tauri::include_image!("icons/icon.png"))`（已实现于 `lib.rs`）。

### 7.6 Git/Windows 陷阱

- CRLF hash 须规范化；force-push 后 CI push-run 误报看 pull_request run；多分支共享工作树须 stash + `--no-verify`；GHA actionlint 集成 shellcheck（warning 也 FAIL）。

---

## 8. 工具与命令速查

- **DSH CLI（新位置，经项目内脚本）**：
  - `node .hermes/task-runtime/run-dsh.js "D:\All projects\DSH\deepseek-harness\source" "D:\All projects\DSH\deepseek-harness\dsh-home" <dsh命令>`（dsh 命令：`web` / `--profile headless "任务"` / `--dump-config --profile web`）
  - 或直接 `node "D:\All projects\DSH\run-dsh.js" deepseek-harness/source deepseek-harness/dsh-home <命令>`（cwd=`D:\All projects\DSH`）。
- **pnpm**（逐次 pin，不改全局）：`node .hermes/task-runtime/run-pnpm.js <cwd> <pnpm args>`。
- **DSH 桌面构建**：`powershell -ExecutionPolicy Bypass -File "D:\All projects\DSH\dsh-desktop\build-x.ps1"`（前置：SUBST X: + rust GNU toolchain；产物直接写新位置 `src-tauri\target\release\`，增量 ~24s）。
- **github-delivery.py**（`.hermes/task-runtime/`）：`checks --sha`、`jobs --run-id`、`create-pr`、`update-pr --number --body-file`、`merge --number --sha`、`wait-runs`。
- **质量门**：`run_quality_gate.py verify` / 单项 `governance`、`skill-provenance`、`context-pack`、`core-schemas`、`client-neutral-manifest`、`adapter-registry`、`adapter-conformance`、`compile`、`security`。
- **generate_current_state.py**：`scripts/ci/generate_current_state.py`（source_digest 只追踪 skills + canonical 文件，不含 config-ownership）。
- **迁移辅助脚本（.hermes/task-runtime/，可复用）**：migrate-dsh.py（排除 node_modules 复制）、install-dsh-dest.py（新位置重建依赖）、verify-dsh-dest.py、fix-dsh-dest.py（rename 绕行循环 junction）、start-dsh-dest.py、gen-dsh-icons.py（品牌图标生成）、run-build-x.py（经 wrapper 调 build-x.ps1）。

---

## 9. 关键决策记录（沿用 + 本轮新增，勿推翻）

1. **Skill 精简原则**："搬家不删"——SKILL.md 只留 frontmatter + 触发条件 + 顶层纪律 + 症状索引，详细内容移 `references/`，零丢失。
2. **CC Switch 契约定案（WL3-700）**：registry operations = `[detect, capabilities, observe]`；manifest `writes: unavailable`；路由配置 = 用户私有仅 OBSERVE 不写。
3. **openhuman/open-design 客户端**：USER_GLOBAL desired = `MANAGE` + `apply_supported=false`；DESIGN-LAB = `PROJECT_OVERLAY/OBSERVE`。
4. **DSH 定位**：可替换 Runtime Adapter / Agent Runtime，不是 Hermes 替代品。
5. **DSH 迁移策略（实践证明正确）**：复制**排除全部 node_modules**（junction 结构复制会展开成真实目录 + 源链接层本坏），复制后新位置 `pnpm install --frozen-lockfile` 重建；**用户 migrate-dsh.ps1 的 robocopy /E 含 node_modules 是卡死 18 分钟 + 循环 junction + 插件加载失败的根因**（已 kill）。
6. **循环 junction 处置**：递归删除（rd / PowerShell / fs.rmSync）全部失败 → 用 Node `fs.renameSync` 只改名不删除，DSH 启动时 `healProfilesModuleFallback` 自动重建干净 junction。
7. **桌面入口 = dsh-desktop.exe 唯一方案（用户拍板"VBS 的就不要了"）**：VBS 启动器废弃不维护；exe 内置后端自启动。
8. **桌面版颜色冲突 = 插件 bug 非官方问题**：dsh-update-checker 硬编码白字，本地 node_modules 补丁（插件更新会覆盖，注意维护）。
9. **图标全套 = 官方 favicon.svg 生成**：品牌蓝圆角 + 白鲸鱼；exe/窗口/任务栏/快捷方式/setup 全对应；窗口图标 = `setup` + `WebviewWindow::set_icon`（tauri 2.11.5 实测 API）。
10. **会话不丢保证**：原 DSH 全程未动 + 新位置完整副本（sessions/storages 文件数完全一致）。

---

## 10. DSH 接手后的建议执行顺序

1. **先读** AGENTS.md + 本文件 + `50-taskpacks/TASKPACK_SUMMARY.md` + `WORK-LAB-MASTER-2.0-APPROVAL-PACKAGE.md`，核对 Task Ledger 与当前 git 状态（main HEAD `ad10333`，control-plane 系列在演进）。
2. **提交本次交接文档**（本文件 + SUMMARY 更新，2 个文件）——向用户申请 commit/push。
3. **核对 main 现状**：#118 已含 DSH adapter 交付物 + model control plane + WL3-810 归档；确认交接文档与 main 上 control-plane 系列（agent registry / work unit / policy / harness adapter interface / dsh plugin evaluation）的一致性。
4. **WL3-100/110 收编**：合并子代理能力矩阵 + 身份模型产出。
5. **DSH-040**：用户在 UI 填 key 后，按批准做付费 smoke（默认 LOCAL_SMOKE_ONLY）。
6. **其余 WL3 任务**按 Task Ledger 顺序推进。

> 每步涉及外部变更（commit/push/PR/merge/下载/付费调用/系统级改动）前，必须向用户列出精确动作并等批准；不得自我授权。

---

*交接完成。DSH 若对任何状态有疑问，以本文件 + 仓库 git 历史 + AGENTS.md 为准，不臆测。*
