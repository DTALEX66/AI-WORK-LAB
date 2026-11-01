# WORK-LAB Master TaskPack v2.0 — 交付总结与错误记录（2026-08-11 晚）

> 状态：`MERGED_TO_MAIN`（PR #51 / #52）
> 最终 main head：`e783e470bccdf0622d5f4422695e70a69a0429d1`
> 本地/远端：已同步，工作树干净，AHEAD_BEHIND=0/0

## 1. 交付摘要

### 已合并到 main 的 PR

| PR | 标题 | merge commit | CI |
|---|---|---|---|
| #51 | feat: stage3 continuation — contract reconciliation, Codex overlay, native Tauri build | `1bda8ed` | 5/5 success |
| #52 | feat(wl3-420): workspace active-project discovery for Observer | `e783e470` | 5/5 success（exact-SHA + main） |

### 28 个 WL3 任务最终状态（截至本轮）

```text
VERIFIED_LOCAL:                      27（WL3-000..710、800、810、620 原生构建闭环）
LOCAL_VERIFIED_READY_FOR_APPROVAL:    1（WL3-820 批准包）
```

**WL3-620 完整闭环**：rustc 1.88.0 + MSVC 14.44 + WebView2（已有）→ app.exe（PE32+ 9.1MB，SHA `1319d54c...`）+ MSI（`90f68c00...`）+ NSIS（`fc1e5c6d...`）→ 安装→运行→窗口→卸载全生命周期验证 → Release `v0.1.0-native-observer`。

### 本轮核心交付物

**1. Codex 用户覆盖配置（任务一）**
- `sync_codex_global_assets.py` plan → apply → verify：`.codex\AGENTS.md` managed block、`.codex\rules\workflow-assistance.rules`、10 个 `workflow-assistance-*` 技能
- 用户 config.toml 三字段（approval_policy/sandbox_mode/project_doc_max_bytes）识别保留，auth/session/provider 未触碰
- Hermes 配置检测：doctor 全绿，Codex 配置的 4 个 cron 任务已载入运行

**2. 总工作区发现 + 活跃项目检测（WL3-420 扩展，用户核心需求）**
- `active_projects.py`：扫描用户指定总工作区（`D:\All projects`）注册全部 Git 项目；agent 进程运行 + 项目内 `.hermes/.codex/.agents` 证据新鲜度（120 分钟）判定 ACTIVE
- 实测：注册 2 项目（work-lab + open-design-assistance），work-lab 因 Hermes 运行 + 新鲜证据标记 ACTIVE
- 只读边界：不读文件内容、不碰凭据/会话/正文，fail-closed

**3. Observer 实时显示修复（用户"发布前必须测试"要求）**
- 发现 dashboard 渲染与 canonical schema 脱节（旧事件库 vs canonical 投影），修复：
  - `observer_canonical.py`：projects 输出前端 `state` 词汇 + usage series/inputTokens
  - `observer_dashboard.py`：`_render_full/_render_compact` 重写为 canonical schema
  - `canonical_store.py`：usage total_tokens 自动派生
- **实时链路实测**：SSE `http://127.0.0.1:2660/api/v1/events` 订阅 → 写入 telemetry → 推送反映（13→15）→ dashboard API `mode: LIVE` 实时显示
- 浏览器验收：`/?view=full` 显示 WORK-LAB(running) + OPEN-DESIGN(idle)、用量 2050、CI 1 次

**4. 原生 Tauri 构建（WL3-620）**
- 工具链安装到 `D:\All projects\OS Environment`（用户指定）：rustup 1.77.2 → 1.85.0 → **1.88.0**（tauri 2.11.x 依赖链要求 edition2024）、MSVC Build Tools 14.44
- cargo test 1/1（修复 IPv6 `[::1]` loopback 校验缺陷）
- app.exe 真实启动验证：主窗口 "WORK-LAB Observer"（句柄 1909488）
- MSI per-user 安装→运行→卸载闭环（无残留）
- GitHub Release `v0.1.0-native-observer`（4 资产，下载读回 SHA 匹配）

**5. 测试**：Observer Python 48/48 · Node UI 44 + 组件 4 · runtime-convergence 104 tests · 新增 test_active_projects(5) + test_observer_dashboard_render(4)

## 2. 错误记录（error-ledger）

**42 条**（ERR-001..042），新增 ERR-037..042：

| ID | 分类 | 问题 | 修复 |
|---|---|---|---|
| ERR-037 | feature_gap | Windows 进程表无 cwd，活跃检测无法从进程路径判断 | 改为 agent 进程运行 + 项目内证据新鲜度 |
| ERR-038 | contract_drift | API 返回 status(ACTIVE) vs 前端读 state(running)，UI 全零 | observer_canonical 输出 state 词汇 + series |
| ERR-039 | contract_drift | Python dashboard 读旧事件库 schema → "暂无观测事件" | 重写渲染为 canonical schema |
| ERR-040 | contract_drift | tauri 2.11.3 依赖链 edition2024 与 rust 1.77.2 不兼容 | 升级 rustc 1.88.0（tauri 合同版本不变） |
| ERR-041 | evidence_state | IPv6 `[::1]` host_str() 带方括号 → loopback 校验失败 | 用类型化 url.host() |
| ERR-042 | ci_configuration | PR 后 CURRENT_STATE digest 不匹配 → CI 失败 | 重新生成 CURRENT_STATE 推送 |

## 3. 交接与续接点

### 已验证成立的运行时

```text
实时链路: canonical store → sidecar(SSE :2660) → Observer dashboard(:6522) → 页面 LIVE
          （写入即推送，实测 13→15；mode=LIVE 持续）
常驻进程: sidecar PID 23692（动态端口）、observer dashboard 6522 —— 由 Workflow 侧持有
```

### 续接边界（诚实声明）

```text
1. freshness 标签在 LIVE 模式下显示 STALE：快照语义，不影响数据实时性（待优化）
2. 活跃检测 freshness 窗口 120 分钟为启发式；仅编辑器打开无 agent 写入不算活跃
3. 代码签名不适用（个人使用项目）
4. 安装包未做生产签名；SmartScreen 需"仍要运行"
5. 正式生产 release（非 native 前缀）PENDING_HUMAN_APPROVAL
```

### 运行依赖

```text
- Rust 工具链: D:\All projects\OS Environment\.rustup/.cargo（rustc 1.88.0）
- MSVC:        D:\All projects\OS Environment\BuildTools
- 构建缓存:    .hermes/task-runtime/cargo-target（项目内 ignored）
- release:     v0.1.0-native-observer（EXE/MSI/NSIS/SHA256SUMS）
```

## 4. 证据链

```text
PR #51:   staged tree f963d721 → commit 83b30fe4 → 409f4ad（CS regen）→ merge 1bda8ed
PR #52:   commit 5e447c0 → 50b028e（dashboard 修复）→ 65dbcd8（CS regen）→ merge e783e470
CI:       PR #51 run 31474823049 5/5 · main 31474939750 5/5
          PR #52 run 31479768924 5/5 · main 31479873785 5/5
Release:  v0.1.0-native-observer（tag @ 1bda8ed，4 assets 下载 SHA 匹配）
Ledger:   amendments=13 · WL3-620=NATIVE_BUNDLES_READBACK_OK
Freshness: PASS（source_digest fe0f68d3...）
```
