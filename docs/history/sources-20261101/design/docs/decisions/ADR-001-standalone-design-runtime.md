# ADR-001: Standalone-first Design Runtime

- 日期：2026-09-04｜状态：ACCEPTED｜任务：DL-TP-R0-008

## 背景

DESIGN-LAB 曾依赖/提及 WORK-LAB、ArcheAxis 等跨项目组件。任务包 DL-TP-20260904 裁决：DESIGN-LAB 必须能在二者未安装时完成完整设计生产闭环。

## 决策

1. DESIGN-LAB 拥有完整设计域 Adapter 与 Local Runtime（控制平面、状态、Adapter、审批、证据、UIA 全在本仓库）。
2. WORK-LAB / ArcheAxis **默认关闭**；DESIGN-LAB 启动、测试、恢复、Golden Workflow 不探测也不要求外仓。
3. 外部项目只能通过**版本化公共合同**连接（Schema/API/Manifest），不读私有 DB 或目录。
4. 运行/证据/缓存根统一为 `PROJECT_LOCAL_ROOT`（`.project-local/`）；`.hermes` 不再作为活跃写入路径。
5. 联邦（ArcheAxis 知识出口等）仅在显式批准 + 权利检查后经合同进行。

## 后果

- 正面：单仓可自举、可复现、不依赖未安装组件；边界清晰。
- 负面：需迁移既有 `.hermes` 写入路径（R0-003）；旧引用文档需标记 superseded。

## 参考

- DESIGN-LAB-COMPLETE-REPAIR-AND-MIGRATION-PLAN v2.5；DL-TP-20260904 §0；AGENTS.md
