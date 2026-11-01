# WORK-LAB 交接总结（2026-08-19）

> 覆盖 2026-08-18 晚至 08-19 的 Observer 前端重构、DSH 迁移、三项目分层决策与控制平面补全。

## 1. Observer 前端重构（React 控制塔）

- 新前端：`30-observer/work-lab-observer/frontend/`（Vite + React + TS + Tailwind + Recharts + shadcn 风格组件）
- 构建：`pnpm build` → `frontend/dist`（Tauri 打包目标改为 dist）
- 8 个导航视图（总览/智能体/执行/模型/记忆/工具/监控/设置），全部接入真实数据
- 数据源：
  - snapshot API（sidecar :61867）→ 项目/执行/Token/成本/治理/历史/传输
  - Prometheus（:9090）→ KPI 走势/成本折线（query_range 真实时间序列）
  - metrics_exporter 新增系统资源（psutil：CPU/内存/磁盘/网络）
- 全中文界面 + 人民币成本（USD→CNY 参考汇率 7.2）
- 关键 bug 修复：snapshotToTimeline 里 revision 是数字 1261，`(revision||'').slice` 抛错中断 load 导致 Token/成本显示 0 → `String(revision)`
- 预览：http://127.0.0.1:8090 与 8089（serve frontend/dist，no-cache）

## 2. DSH 迁移（完成）

- DSH 本体迁到 `D:\All projects\DSH`（source/dsh-home/launch/pnpm-store/run-dsh.js/dsh-desktop）
- pnpm-store 移动保留硬链接，storeDir 全部更新（.modules.yaml ×2 + pnpm 全局 config）
- WORK-LAB 内旧 DSH 已清理（释放 ~5GB）
- 桌面快捷方式图标修复（tauri icon.ico）
- DSH 视觉模型切本地 Ollama qwen2.5vl（vision.env）

## 3. 三项目分层决策（v5 最终）

- `00-governance/THREE_PROJECT_LAYERING_DECISION.md`（v5）：知识中心 + 分阶段演进
  - 所有可转化知识最终归 ArcheAxis（唯一真源），人类学习侧留在 ArcheAxis
  - WORK-LAB/DESIGN-LAB = 调用 + 归档（转化器，开放集合）
  - 阶段 1 现有资产归各自所有，阶段 2 OS 完整后逆向归档
- 已推送到 ArcheAxis（docs/cross-project/）+ DESIGN-LAB（project-memory/cross-project/）
- 审计/未来蓝图分析：THREE_PROJECT_LAYERING_AUDIT / FUTURE_BLUEPRINT_ANALYSIS

## 4. 控制平面补全（2026-08-18 白天）

- Sandbox Manager（Level0-3）+ MCP Gateway（工具治理）+ 测试
- codex/hermes/acp Adapter 对齐 Harness 接口
- Memory 治理 v5 定位（客户端适配记忆，长期知识归 ArcheAxis）
- 减法审计（无知识本体需删，62 SKILL.md 为阶段 2 逆向归档候选）
- ArcheAxis API 契约调研 + 逆向归档流程模板

## 5. 运行方式

- Observer 前端：http://127.0.0.1:8090（或 8089）
- 观测栈：start-services.ps1（Grafana/Prometheus/Loki/OTEL/metrics/sidecar）
- 收集器：durable_worker 绑定 Observer 桌面版生命周期（CREATE_NO_WINDOW）
- 桌面版：`30-observer/work-lab-observer/gnu-target/release/app.exe`

## 6. 待办（后续）

- Observer 前端集成 Tauri（tauri.conf.json frontendDist → frontend/dist，重建 app.exe）
- 阶段 2 逆向归档（等 ArcheAxis 完整）
- 6 个 commit 已提交待 push（本次交接同步）