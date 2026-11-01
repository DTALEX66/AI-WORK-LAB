# DESIGN-LAB：独立审计与 Codex 执行包

**只给本项目使用，不依赖另一项目包，也不需要双项目总控指令。**

这是 2026-09-22 既有审计材料的拆分交接。本次仅整理文件和校验完整性，没有重新审计云端或执行产品测试；原审计范围、证据冲突、未覆盖项和 Owner 权限边界全部保留。

## 使用

在本项目对应的 Codex 会话中提供这个 ZIP（或解压目录），发送 `03_START_PROMPT.txt`；完整任务指令是 `02_CODEX_EXECUTION.md`。本包所有执行必需的交接文件已经配齐，G0/G1/G2 也已改为本项目独立任务。

不要把包整体覆盖到项目根目录；它是交接资料，不是源码补丁、产品安装包、B10 视觉素材包或另一个可变权威账本。实际仓库、设计参考和实机资源仍按已批准路径读取；包内路径线索不构成额外访问授权。

## 文件

| 文件 | 用途 |
|---|---|
| [00_START_HERE.md](00_START_HERE.md) | 本项目使用入口与文件说明 |
| [01_CLOUD_AUDIT.md](01_CLOUD_AUDIT.md) | 本项目审计结论、历史约束和未核验范围 |
| [02_CODEX_EXECUTION.md](02_CODEX_EXECUTION.md) | 可直接粘贴的完整独立执行指令 |
| [03_START_PROMPT.txt](03_START_PROMPT.txt) | 上传本包后的短启动语 |
| [05_EVIDENCE_LEDGER.json](05_EVIDENCE_LEDGER.json) | 本项目只读证据记录；不是项目状态账本 |
| [06_AUDIT_COVERAGE.csv](06_AUDIT_COVERAGE.csv) | 本项目审计覆盖与剩余范围 |
| [07_LOCAL_RECONCILIATION_CHECKLIST.md](07_LOCAL_RECONCILIATION_CHECKLIST.md) | 工作树、未上传内容、资料和安装位置保护 |
| [10_TASKS.json](10_TASKS.json) | 本项目任务依赖；无另一项目任务依赖 |
| [11_SOURCE_INDEX.md](11_SOURCE_INDEX.md) | 本项目来源定位与共享视觉参考定位 |
| [12_PACKAGE_ORIGIN.json](12_PACKAGE_ORIGIN.json) | 来源包摘要与拆分记录 |
| [SHA256SUMS.txt](SHA256SUMS.txt) | 包内文件校验值 |
| [08_DESIGN_APPSHELL_MIN_REPRO.mjs](08_DESIGN_APPSHELL_MIN_REPRO.mjs) | 已保存的 AppShell 最小逻辑复现 |
| [09_DESIGN_APPSHELL_MIN_REPRO_RESULT.json](09_DESIGN_APPSHELL_MIN_REPRO_RESULT.json) | 该最小逻辑复现的历史执行结果 |
| [13_PREVIOUS_EVIDENCE_NOTES.md](13_PREVIOUS_EVIDENCE_NOTES.md) | 早一轮本项目证据与 D6–D8 检查说明 |
| [14_BRANCH_TIP_COUNTEREXAMPLE.json](14_BRANCH_TIP_COUNTEREXAMPLE.json) | 独立 SQL 反例，不是产品测试 |
| [15_CI_E2_ARTIFACT_READBACK.json](15_CI_E2_ARTIFACT_READBACK.json) | 历史受控浏览器 CI 摘要 |
| [16_ORIGINAL_CI_E2_ARTIFACT.zip](16_ORIGINAL_CI_E2_ARTIFACT.zip) | 保存的原始 CI artifact |

## 完成边界

先保存本地未上传工作，再核对 live refs/现行权威，按可复现证据修复。没有运行的测试明确 NOT_RUN；合成与受控测试不冒充实机或人审。继续遵守禁止擅自发布、迁移、跨仓写入与覆盖本地可用产品的约束。
