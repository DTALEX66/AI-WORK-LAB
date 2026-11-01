# WORK-LAB｜MONITORING-INTAKE-20260915 未完成任务登记

登记日期：2026-09-15。性质：**AUDIT_RECOMMENDATION_ONLY 登记，不是新的权威 TaskPack**，不授权安装、付费、修改生产或替换。
来源：桌面 07_WORK-LAB_工作区接入交接.md / 01_审计报告与三项目融入建议.md / 05_附件完整性与工作簿审计.json（MONITORING-INTAKE-20260915）。
原始上传附件 SHA-256 以 05 JSON `input_files` 为准（7 文件含 xlsx 工作簿）；完整原任务映射见 03_43条原任务_去重映射.json（未上传，UPLOAD_REFERENCE_ONLY）。

## 0. 治理状态

CODEX / DSH / HERMES 三方治理任务**暂时告一段落**（用户 2026-09-15 声明）：
- DSH→Hermes ✅（763da68）· Hermes→Codex ✅（b4a18c4 / 2940586 / 7bee499 / fa9f312，双端一致 CI 12/12×2）
- 未做：Codex→DSH 段、DSH 对 Hermes 写入面的独立复核、工具执行层合成验收（沙箱 ACL 环境阻塞，需桌面重跑或授权 runner 访问 C:\Users\Default）
- 后续是否续段，等用户新指令；本登记不派工。

## 1. 事实核实（本地已验证，2026-09-15）

| 07 声称 | 核实结果 |
|---|---|
| radar_core blob=42e62052 | ✅ HEAD:services/radar/radar_core.py 完全一致（无漂移） |
| 根 AGENTS 仍含 10-workflow 旧路径 | ✅ L9（scope 根声明）+ L79（execution contract）仍在；`10-workflow/` 0 个 tracked 文件，磁盘仅 1 个陈旧 untracked `__pycache__/*.pyc` |
| services/radar/ 模块 | ✅ radar_core.py / radar_scoring.py / auto_poc_routing.py 在册 |

注意：F04 上轮只修了 AGENTS L88 门禁命令路径；**L9/L79 根声明残留属于本登记的未完成任务**（本轮不擅改 AGENTS，治理已告段落；修改需下次治理授权）。

## 2. WORK-LAB 未完成候选（按 01/07 分流，登记不派工）

| ID | 内容 | 边界 | 状态 |
|---|---|---|---|
| WL-R01 | 在现有 radar_core 上补证据/差分/覆盖（不建后台） | 离线 | ✅ 已做：新增 `services/radar/radar_observations.py`（Observation 账本 + F1 差分/F2 unknown 语义/F3 SourceReport/F4 PriceRecord 时效/F5 按 entity_kind 路由排序），纯 sidecar 不改 17 字段 Candidate，test_radar.py +9 测试全绿 |
| radar_core 静态缺陷 ①–⑤ | discover() 丢更新 / unknown 混同 / available() 混淆空与不可用 / 无价格时效 / min_stars 不通用 | 增量 sidecar，不推倒框架 | ✅ 已做：全部 5 项在 radar_observations.py 观察层实现，radar_core.py 与既有 13 契约测试零改动 |
| WL-R02 / WL-R06 / W01 / W04 | 只查**实际在用**的 ACP/MCP/AG-UI 及模型别名；按提供方测 load/fork/cancel/perms；AG-UI 按子包破坏性变更核查锁文件与 imports；codex-acp 实现版本≠协议版本 | DeepSeek 静态；Codex 联调 | 未做 |
| WL-R04 / WL-R05 / W03 | 假工具/假凭据/合成事件测越权拒绝、重复事件、恢复 | 离线 | ✅ 部分已做：`e_drive_guard.py`（LESSONS 登记的强制拦截钩子）此前 **0 测试** → 新增 `test_e_drive_guard.py` 11 项合成负载测试（越权拒绝/显式授权/大小写/嵌套/误报/恶意 JSON）；R05 重复事件/恢复由既有 `test_task_ledger_replay.py` 8 场景已覆盖（验证绿）。Codex 实机取消仍待授权 |
| WL-R07 / W07 | 模型/API 表改为带时效/供应方/币种/地域/计费模式的价格记录；未知费用不填 0；工作簿 4 项边界加固（小数调用次数、计价除数 0、语音负时长、无数据验证/表保护）→ 加固前不得当执行预算引擎 | DeepSeek 离线；真实 usage 需授权 | **已做（离线）**：`services/radar/price_validation.py` 落实审计 §7 的 4 项边界拒绝规则 + 未知费用保持 UNKNOWN 不填 0，`test_price_validation.py` 18 项全绿，接预算引擎前加固到位；**待授权**：真实 usage 填写 + xlsx 工作簿原件的数据验证/表保护 |
| WL-R03 | 运行状态四组对照：先旁路观察/确定性重放（tracelab 模式），收费四臂实验仅在必要时且需批准；不重建 TaskStore/TelemetryStore | 付费需批准 | 未做 |
| W05 / W06 / Bolt | Kimi 权益（订阅≠免费 API）、Agents API 可选执行器（本地任务状态/产物导出/费用边界保留）、Bolt 仅脱敏一次性原型 | 只读准备；真实接入需授权 | 未做 |
| 恒定约束 | Observer 保持只读；候选"值得 POC"不自动触发安装/写 TaskPack/PR/生产替换；W02 与 WL-R03 不混为一个因果实验；每实验初始预算 0 不改全局模型政策 | — | 约束 |

其他两项目（ArcheAxis Green 闭环、DESIGN-LAB 设计资产验收）不在本项目登记内，按 01 §8 各自边界。

## 3. 带病登记（与上述无关的既有项）

- ~~5 项既有 Windows 环境测试失败~~ **2026-09-15 新定性：顺序相关 flaky，非真缺陷**——test_machine_identity + test_workflow_governance(portable-install) 4 项**单独跑全绿**，仅在全 suite 特定顺序下失败（前序测试污染全局状态）。同批 `test_sidecar_v3_snapshot`(watcher rollback) 亦为顺序相关 flaky。全量回归 1235 通过、唯一失败为该 flaky。根因待单独排查（疑似 cwd/sys.path 或临时 HOME 污染），暂登记不阻塞
- **2026-09-16 纠正（NF-02 CI 原始日志）**：CI run `34993528858` job `workflow-assistance` 的 `Ran 22 tests FAILED (errors=9)` 全部是 `ModuleNotFoundError: No module named 'services'`——**并非**上行的顺序污染，而是 WLR-058 新增的 `services/radar/radar_observations.py` 顶层 `from services.radar.radar_core import …` + `test_radar.py` 3 个新方法的 `from services…` 直接导入，违反仓库"gate 直跑 test 文件、按文件路径 `_load()` service"的铁律（本地 pytest 从根跑故绿、gate 独立 runner 才炸）。**已修**（3 文件回到文件路径约定，零功能改动），隔离 venv 复现 gate 10/10 + 全量 1255 全绿。上行的 5 项本地顺序相关 flaky 仍单独保留（另一现象，不与 CI 9-error 合并）
- 14 个技能 `.bak` 备份删除——仍无授权
- 工具执行层合成验收 BLOCKED（沙箱 ACL，C:\Users\Default 权限 5）

## 4. 停止点

本登记**不构成派工、安装、付费或生产替换授权**；导入批准≠下载批准≠付费执行批准≠宿主控制批准≠生产替换批准。
下一步由用户决定：续治理段、启动 WL-R01 离线 Radar 样本链、或两者都停。
