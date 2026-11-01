# SESSION-HANDOFF-P0C-20261006

> 只读交接记录，不授予任何权限。
> 分支：`task-decomposition/atlas-gap-archive-20261001`（PR #162），起点 `b0fc828`。
> 范围：闭合 Observer 三项未证项中的 **P0-C（U19 真实桌面表面证明）**。
> 结论：**未闭合**。harness 修好了、仪器 bug 撤回了、黑屏定性了，但**根因未定位，U19 仍记 FAIL**。

---

## 0. 一句话结论

**前端产物没问题，黑屏只发生在打包后的 Tauri release 路径。**
同一份 `dist` 在普通 Chrome 里完整渲染（3,387 色、近黑 0.00%），在 release 二进制里只画出背景色（41 色、近黑 100%）。

---

## 1. 决定性对照（本轮最重要的数字）

| 指标 | 普通 Chrome 打开同一份 dist | Tauri release 二进制 |
|---|---|---|
| 渲染后 DOM | **10,736 B**（侧边栏、WL 品牌块、全部路由按钮齐全） | — |
| 截图尺寸 | 1280×820 | 1600×1025（修正后的客户区） |
| 不同颜色数 | **3,387** | **41** |
| 主色 / 占比 | `#050d16` / 44.66% | `#08090a` / **99.99%** |
| 近黑像素 | **0.00%** | **100%** |

复现命令（证据在 `.project-local/runs/p0c-diag-20261006/`）：

> 2026-10-07 更正：仓库根的这个路径已不在磁盘上。原件没有丢——它随 2026-10-06 的 WorkBuddy 工作树导入保存在
> `.project-local/imported-from-workbuddy-20261006/WORK-LAB__task-decomposition-atlas-gap-archive-20261001-381e33ec/.project-local/runs/p0c-diag-20261006/`
> （含 `bitblt_screen__logical.png`、`capture_modes_nocdp.json`、`chrome_dump_dom.err` 等 30 余项，逐文件 sha256 与来源一致：onlySrc=0、onlyDst=0、contentDiff=0，见同目录 `MANIFEST.md`）。
> 本仓库根下不存在同名目录，是因为那轮实验运行在另一个工作树里；按导入路径读取，不要按本行原句的路径读取。

```
# 供出同一份 dist
cd apps/observer/frontend/dist && python -m http.server 41874 --bind 127.0.0.1

# 独立浏览器渲染
chrome --headless=new --disable-gpu --no-sandbox --user-data-dir=<全新目录> \
  --window-size=1280,820 --virtual-time-budget=10000 \
  --dump-dom "http://127.0.0.1:41874/index.html?view=full&mode=UNKNOWN&theme=dark&shell=tauri"

# release 二进制侧：走 harness 的 GDI 取证
python apps/observer/scripts/u19_webview_e2e.py
```

产物：`chrome_dump_dom.html`、`p0c-chrome-render.png`、`p0c-black-screen-probe.json`、
`p0c-navigate-compare.json`、`p0c-cdp-direct.json`。

---

## 2. 已排除（每条都有实测，不是推断）

| 假设 | 结论 | 依据 |
|---|---|---|
| 会话隔离 / Session 0 黑屏 | **排除** | `session=2`、`WinSta0\Default`、交互式桌面存在、`GetShellWindow` 有值 |
| `lib.rs` 的 `on_page_load` → `webview.navigate` 把页面带白 | **排除** | 设 / 不设 `WORK_LAB_OBSERVER_API_URL` 两次**同样空白**（一次受控配对实验） |
| 前端资源没打进 exe | **排除** | exe 字节内含 `assets/index-DSUnrSyS.js` 与 `view=full&theme=dark&shell=tauri` |
| WebView2 运行时损坏 | **排除** | 同一运行时在 dev-server 路径（Qoder）正常渲染 |
| 代理污染 CDP | **排除** | harness 的 `_cdp_http_get` 本就用原始 socket 绕开 urllib；且端口**从未监听**（10061） |

## 3. 未排除（按可能性排序）

1. **`app.security.csp` 对打包资产 origin 的求值** —— 当前 CSP：
   `default-src 'self' http://127.0.0.1:* http://localhost:*; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:* http://localhost:*; font-src 'self'`
   dev 走 `http://localhost:1420` 命中白名单，release 走 Tauri 打包资产 origin 可能不命中。
2. **Tauri 自定义协议层** —— 打包资产经 `tauri://` / `http://tauri.localhost` 提供，与 http 协议行为不同。

**为什么坐实不了**：release 构建**没有 CDP 端点**。`apps/observer/src-tauri/Cargo.toml` **没有 `[features]` 段**，即未启用 `devtools`，所以 release 二进制不暴露调试端口 —— 拿不到 console / network / exception。这是**构建配置**使然，不是环境或运行时故障。

---

## 4. 我本轮犯的错（含已撤回的假发现）

| # | 错误 | 性质 | 处置 |
|---|---|---|---|
| 1 | `_gdi_render_proof` 用 `w * 12 >= 1280 * dpi` 推断坐标空间（`12` 是 `96` 的笔误） | **我引入的 bug** | 已修 + 已撤回结论 |
| 2 | 据此得出"BitBlt 拍到 375/635/722/384 色真实 UI" | **污染结论** | **已撤回** |
| 3 | 误判 PrintWindow 可作取证手段 | 假设错误 | 实测推翻：4 种 flag × 2 尺寸均 1–2 色 |
| 4 | 误以为置顶后 `GetForegroundWindow` 会变成被测窗口 | 假设错误 | 实测：Windows 前台锁，后台进程抢不到激活；前台是豆包/Qoder |
| 5 | 怀疑代理导致 CDP 失败 | 假设错误 | 端口从未监听，且 harness 本就绕过 urllib |
| 6 | 把静态服务起在 4173（已被 DT ALEX 作品集占用），拿到 404 | 操作错误 | 换 41874，资源全部 200 |
| 7 | 用相对路径给 `--screenshot`，Chrome 写不出文件 | 操作错误 | 改绝对 Windows 路径 |
| 8 | 先做像素取证、后才想到"用浏览器真正看一眼" | **方法错误** | 用户指出后纠正；也正是这一步拿到了决定性证据 |

### 错误 #1 的完整机理（值得记）

本进程已调 `SetProcessDpiAwarenessContext(PER_MONITOR_AWARE_V2)`，此时 **`GetClientRect` 返回的已经是物理像素**
（主窗 `1600×1025` @ `GetDpiForWindow=120`，即 1280×820 逻辑 × 1.25）。
我写的判据却得出"这是逻辑值"，**再乘一次 1.25** → 为 1600×1025 的窗口分配了 **2000×1281** 的位图。
`BitBlt` 于是把窗口右/下边缘之外 **400×256 px 的桌面和邻窗**一起拷了进来 —— 那些"375–722 种颜色"
**没有一个是 Observer 画的**。讽刺的是修好后结论更糟：证明黑屏不是测量假象。

修法：`scale` **仅在 `dpiAwareProcess` 为假时**生效；`captureSize` 用 `min(实测客户区, 缩放值)` 夹紧；
逐窗记录 `sizeAsRead / captureSize / scaleApplied / dpi / expectedPhysicalWIfMain` 供事后审计。

---

## 5. 本轮落地的改动

- **`apps/observer/scripts/u19_webview_e2e.py`**（+299 / −28）
  - 新增 `resolve_app_exe()`：先解析 `CARGO_TARGET_DIR`（相对则相对 cwd 解析）→ `{td}/release/app.exe`，
    回落 `src-tauri/target/release/app.exe`；要求产物 mtime 新于 `tauri.conf.json` + `Cargo.toml` +
    `src/**/*.rs` + `frontend/dist/**`，否则 `STALE_OR_MISSING_BINARY` → **FAIL 而非照拍**。
    记录每候选 `bytes|mtime|sha256|newerThanAllInputs` 与 `chosen`。
  - `_gdi_render_proof` 重写：DPI 感知状态显式记录；screen BitBlt（唯一能拍到 WebView2 的路径）+
    PrintWindow（仅作交叉核对，已不能单独定案）；置顶后回读 `GetForegroundWindow` 做遮挡自证，
    遮挡即记 `occludedNotCounted`；抓图矩形永不超出实测客户区。
  - 新增模块常量 `WINDOW_LOGICAL_WIDTH_PX = 1280` 仅用于自证坐标空间。
- **`taskpacks/current/error-ledger.json`**：新增 **ERR-101**（仪器抓图矩形越界）、**ERR-102**（release 空白、根因未定），
  `total` 99 → 101，`by_classification` 同步。`scripts/ci/verify_error_ledger.py` → `ERROR_LEDGER_PASS entries=101`。
- **`taskpacks/current/OPEN-TASK-REGISTER.md`**：新增行 `U19-P0C-20261006`。
- 本文件。

`apps/observer/src-tauri/Cargo.toml` 显示为 modified 但 **无内容 diff**（仅 CRLF 统计缓存），不应被提交。

---

## 6. 门禁状态（本地，非 exact-SHA CI）

| 组 | 结果 |
|---|---|
| `observer-web-contracts` | **FAILFAST_GROUP_PASS** 10/10（Node v24.18.0） |
| `observer-python-skeleton` | **FAILFAST_GROUP_PASS** 8/8（wl-py311 / Python 3.11.15） |

**坑**：`scripts/ci/failfast_group.py` 从 PATH 挑解释器。若未把
`.project-local/toolchains/wl-py311/Scripts` 前置到 PATH，它会挑到托管 3.13.12 并因缺 `jsonschema`
让 `tests/test_observer_runtime.py` **假失败**（`FAILFAST_GROUP_FAIL ... failed_cmd=3 exit=1`）。
这不是仓库缺陷。**本地 QUALITY_GATE_PASS ≠ CI 绿。**

---

## 7. 明确未闭合

1. **P0-C 根因未定位**（CSP vs 自定义协议层）—— 需启用 Tauri `devtools` 特性才能拿到 console，**属构建配置变更，未获授权**。
2. P1 遗留（均未授权，未动）：气泡右缘夹取、本地门禁对 Node 契约组的覆盖、其他窗口尺寸未测、
   其他客户端 live 部署与回读、merge main 需授权、AG-15/16/17/10/11、AG-19 历史原件恢复。
3. 文档任务（两份 2026-10-06 文档：完整项目描述与未来蓝图 / 权威修复双端描述同步）**尚未开始**——
   本轮按用户决定"先提交 U19 修复"优先处理了 P0-C。蓝图 docx 已提取并校验
   sha256 `f3784a9950adce06e8d87015a0ecb39d1ed4fdb3b93d5ccd3c9b40398bea3440`（与提示词声明一致）。

---

## 8. 下次接手的恢复清单

1. `git fetch` → 解析 `origin/main` 与交付分支 exact SHA。
2. 按序读：`WORK-LAB-AUTHORITY.md` → `.project/governance/project-authority-index.json` → `AGENTS.md`
   → `.project/governance/taskpack-authority-index.json` → `taskpacks/current/OPEN-TASK-REGISTER.md`。
3. 工具链铁律：Python 用 `.project-local/toolchains/wl-py311/Scripts/python.exe` 并**前置到 PATH**；
   Node 显式加 `D:\All projects\OS External Configuration\10-toolchains\scoop\apps\nodejs-lts\24.18.0`。
4. 不要重跑历史审计；直接从第 7 节挑一项。
5. 若继续 P0-C：唯一建议动作是**启用 Tauri `devtools` 特性后读真实进程的 console**，
   在那之前任何"根因是 X"的说法都只是推测，不得记为结论。

---

## 9. 交接提示词（可直接复制）

```
# WORK-LAB 续接：闭合 P0-C（U19 真实桌面表面证明）根因

## 起点
- 分支 task-decomposition/atlas-gap-archive-20261001（PR #162），先 git fetch 并解析
  origin/main 与交付分支 exact SHA，再按序读 WORK-LAB-AUTHORITY.md →
  .project/governance/project-authority-index.json → AGENTS.md →
  .project/governance/taskpack-authority-index.json → taskpacks/current/OPEN-TASK-REGISTER.md。
- 先读 taskpacks/current/SESSION-HANDOFF-P0C-20261006.md 全文。不要重跑历史审计。

## 已确定（不要重复论证）
- 前端产物无罪：同一份 apps/observer/frontend/dist 用 chrome --headless=new 打开，
  渲染出 10,736 B 完整 DOM、3,387 种颜色、近黑 0.00%。
- 黑屏只在 Tauri release 路径：修正矩形后 BitBlt 得 41 种颜色、#08090a 99.99%、近黑 100%。
- 已排除：会话隔离、lib.rs 的 on_page_load navigate、资源未嵌入 exe、WebView2 运行时损坏、代理污染 CDP。
- release 构建无 CDP 端点：apps/observer/src-tauri/Cargo.toml 没有 [features] 段，未启用 devtools。

## 唯一任务
定位 release 路径黑屏的根因，二选一：
  (a) tauri.conf.json 的 app.security.csp 对打包资产 origin 求值失败；
  (b) Tauri 自定义协议层（tauri:// 或 http://tauri.localhost）行为差异。
做法：启用 Tauri devtools 特性（这是构建配置变更，需先取得用户授权），
读真实进程的 console / network / exception，再定论。

## 铁律（违反即返工）
- Python 用 .project-local/toolchains/wl-py311/Scripts/python.exe，并前置到 PATH
  （否则 failfast_group.py 会挑到托管 3.13.12 并因缺 jsonschema 假失败）。
- Node 显式加 D:\All projects\OS External Configuration\10-toolchains\scoop\apps\nodejs-lts\24.18.0。
- 新仪器必须自证四件事：启动产物 SHA、比所有输入新、拍的矩形及坐标空间、两条独立绘制路径一致。
- Tauri 窗口 width/height 是逻辑像素；per-monitor aware 进程下 user32 已返回物理像素，切勿二次缩放。
- 抓图矩形永不超出实测客户区。
- PrintWindow 拍不到 WebView2 合成表面（实测 4 flag × 2 尺寸均 1-2 色），只能作交叉核对。
- 截图先看内容再当证据。
- 本地 QUALITY_GATE_PASS ≠ CI 绿；必跑
  scripts/ci/failfast_group.py --group observer-web-contracts 与 observer-python-skeleton。
- 铁律测试优先于新功能；不 wholesale merge 旧支；不把 Observer 改成可写；不建第二套设计工作台。
- 移动 taskpacks/current、reports/ 前先 git grep。
- 未拿到证据前，U19 一律记 FAIL，不得伪报 PASS。
```
