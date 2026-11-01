# Observer Package 迁移拆解总结（2026-08-16）

## 来源
`D:\All projects\WORK-LAB-Observer-Package-20260816` —— 云端基线 `fadcded` 的本地审计副本
+ 未提交的安全热修（见 taskpack 第 3 节）。

## 拆解结论
26 文件迁入 → 哈希对比 + 逐行 diff 后，净变更 = **7 个实质修复 + 2 个文档**；
其余 29 个"纯行尾 churn"文件已还原（内容与云端完全一致，仅 CRLF/LF 差异）。

## 实质修复（对应 taskpack P0/P1）

### 后端 P0（3 文件）
| 文件 | 修复 | 门禁 |
|---|---|---|
| canonical_store.py | 平台观测改用稳定键 `platform-{project_id}`，停止每 tick 无界增长 | P0#5 |
| composition_root.py | Git 投影按 `project_id` 分组（`_git_states`+`git_map`），修复跨项目串值 | P0#1 |
| snapshot_api.py | 有 execution 时 REGISTERED/IDLE→ACTIVE，注册≠运行 | P1 |

### 前端 P0（4 文件）
| 文件 | 修复 | 门禁 |
|---|---|---|
| api.js | normalizeV3 同时输出 `tokenSummary`+`usage`，修复真实 Token 被隐藏 | P0#2 |
| state.js | last-good 接受合法 v3 零项目快照，不再假 OFFLINE | P0#3 |
| fusion-v3.js | malformed/dropped/coverage 伪 0→"—"；侧栏图标+文字导航 | P0#4 |
| command-center.css | 黑白中性重设计（+98 行）+ Light 独立 token + 184px 文字侧栏 | 视觉 |

### 文档（2 新增）
- `WORK-LAB-OBSERVER-AUDIT-REDESIGN-2026-08-16.md`（202 行：全量审计 + CC3 设计 + WLO-200/240/280/300 门禁）
- `OBSERVER_PACKAGE_README_20260816.md`（包说明）

## 验证
- 6 个改动文件语法检查：全部通过
- 前端 `run_all_tests.js`：**76 passed, 0 failed**
- 后端定向（canonical_store / sidecar_v3_snapshot / snapshot_validator / collectors / sse_live / durable_worker）：**88 passed + 7 subtests**

## 回滚
迁入前备份：`.hermes/task-runtime/observer-package-analysis/pre-migration-backup/`（26 文件）。
迁移/对比脚本：`migrate-observer-package.ps1`、`compare-observer-package.ps1`。

## 未完成（后续门禁）
- **视觉验证**：WLO-280 截图门禁（Full/Compact × Dark/Light × live/delayed/offline/fixture）。
- **云端推送**：当前环境无法连接 github.com:443（网络受限），push/fetch 均失败。
