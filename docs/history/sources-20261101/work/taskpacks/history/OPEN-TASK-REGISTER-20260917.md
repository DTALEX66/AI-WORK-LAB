# WORK-LAB｜统一未完成任务总账（OPEN-TASK-REGISTER-20260917）

生成：2026-09-17 cutover 收口后，扫描 `taskpacks/current/` 全部现行文档的"未做/待授权/BLOCKED"条目，
归并为单一总账。性质：**登记口径，不构成派工授权**（与 20260915 登记一致：导入批准≠执行批准）。

## A. 已完成（cutover 收口，无需再动）
- 分支收敛 cutover：main=`ac323a2`（唯一 ACTIVE 分支），55 legacy 分支全部退役
  （52 非祖先分支→`wl-retire-20260917/*` 归档 tag + 删除；3 祖先分支直接删除）。PR#124/#125 MERGED。
- BR-RESIDUAL-AUDIT：0 个 live-code 残余（52 SUPERSEDED_HISTORICAL + 3 ABSORBED）。
- Universal Workflow Taskpack 20260916 可自执行片 M0–M3：273/273 测试绿，收口于 `826350f`。
- HERMES-UPDATE-AND-FIXES-20260917：v0.21.2→v0.21.3 更新 + 4 缺陷修复，21 资产 CONVERGED，38/38 gates。

## B. 未做 — 离线可做（不需付费/外发，但需派工指令）
| ID | 内容 | 来源 | 备注 |
|---|---|---|---|
| B1 | 根 AGENTS L9/L79 旧路径（`10-workflow/` 声明）残留清理 | MONITORING-INTAKE §1 | 登记明言"修改需治理授权"；0 tracked 文件，仅陈旧 untracked pyc |
| B2 | 5 项顺序相关 flaky Windows 测试根因排查（test_machine_identity + test_workflow_governance portable-install + sidecar_v3_snapshot） | MONITORING-INTAKE §3 | 单跑全绿、全 suite 特定顺序失败；疑似 cwd/sys.path/临时 HOME 污染；不阻塞 |
| B3 | Codex→DSH 治理段 + DSH 对 Hermes 写入面独立复核 | 2026-09-15 三方治理 | 用户当时声明"告一段落"，待续需新指令 |

## C. 未做 — 待逐项授权（真实外部副作用）
| ID | 内容 | 所需授权 | 来源 |
|---|---|---|---|
| C1 | WL-R02/R06/W01/W04：实际在用 ACP/MCP/AG-UI + 模型别名核查（DeepSeek 静态 + Codex 联调） | 派工（静态可离线；联调需 Codex 实机） | MONITORING-INTAKE §2 |
| C2 | WL-R03：运行状态四组对照（旁路观察→收费四臂实验） | 付费实验需批准 | MONITORING-INTAKE §2 |
| C3 | W05/W06/Bolt：Kimi 权益 / Agents API 可选执行器 / Bolt 脱敏原型 | 真实接入需授权 | MONITORING-INTAKE §2 |
| C4 | Codex 实机 cancel 行为验证（R04/R05 残片） | Codex 实机授权 | MONITORING-INTAKE §2 |
| C5 | Universal Taskpack 6 组真实外部片（真实云发布/第二外部项目/第二执行器/真实多环境节点/付费模型调用/真实 Observer UI+安装+全局部署） | 单卡单副作用收口，逐项授权 | CLOSEOUT-HANDOFF-20260916 §三 |
| C6 | 真实 usage 填写 + xlsx 工作簿数据验证/表保护（R07 残片） | 真实 usage 授权 | MONITORING-INTAKE §2 |

## D. BLOCKED — 环境受限
| ID | 内容 | 解除条件 |
|---|---|---|
| D1 | 工具执行层合成验收 | 沙箱 ACL：需桌面重跑或授权 runner 访问 C:\Users\Default（权限 5） |
| D2 | 14 个技能 `.bak` 备份删除 | 需用户明确授权（带病登记，长期无授权） |

## E. 非阻塞可选项（doctor 余项）
- `state.db` 体积告警：可离线 `hermes sessions optimize-storage`（`sessions.auto_prune` 已 true）
- 可选补 API key 提示：不阻塞使用

## 恒定约束（所有续做项必须保持）
- 治理轻量：Global User Rule + Project Delta + Software Adapter + On-demand Skills；不加第二 ledger/authority/发布器/同步器。
- `.project-local/` 为唯一运行数据边界；Observer 只读；候选 POC 不自动触发安装/PR/生产替换；每实验初始预算 0。
- 进 main 一律走 PR + CI（main 受保护：required review=1 + enforce_admins + strict aggregate）。
