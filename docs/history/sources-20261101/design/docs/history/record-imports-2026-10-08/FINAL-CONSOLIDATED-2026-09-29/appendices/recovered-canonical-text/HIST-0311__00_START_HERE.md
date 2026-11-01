# OPEN-DESIGN-Assistance 最终权威执行任务包 v4.2

生成日期：2026-08-10  
目标仓库：`DTALEX66/OPEN-DESIGN-Assistance`  
Windows 本地目标：`D:\All projects\OPEN-DESIGN-Assistance`  
审计基线：云端 `main@4ae0981b1d75ac1d20cac3a231b7e157854a4fb9`

## 权威性

本包取代旧 V2、V2.1、V3、V4 草案及仅存在于对话或 Library、但未进入目标仓库的任务说明。执行时的事实优先级为：

1. 执行开始时重新读取的 GitHub、本地 Git、Open Design 与 CI 事实；
2. 本包；
3. 仓库当前 canonical 产品定义、Schema 与门禁；
4. `legacy-source/` 中的 V3 包仅作来源和资产回收参考，不可直接整包覆盖。

## 最终定位

> Open Design-first、Agent-compatible 的专业设计智能、视觉质量、商业生产与可编辑交付增强产品。

它不是独立 Lovart、第二套 Open Design、聊天客户端、模型网关、纯知识库或 MiniGame 产品。Open Design 负责用户主入口、项目、Studio/画布、Agent、插件运行、GenUI、Artifact、预览和导出；本仓库负责 Domain Packs、专业方法、视觉质量、评审、权利门禁、生产预检、可编辑交付、Benchmark 和证据。

## 开始执行

```powershell
python scripts\verify_taskpack.py
```

然后把 `01_FINAL_MASTER_TASKPACK.md` 与 `09_AGENT_START_PROMPT.md` 一起交给当前执行协调器。协调器可以是 Hermes、Codex、Cursor、WorkBuddy 或其他兼容 Agent；不得把任务包绑定到某个固定客户端或模型版本。

## 默认模式

- 先只读审计，再在隔离分支或 worktree 实现；
- 单一 writer；研究和只读验证可并行；
- 不自动 live apply、commit、push、开 PR、merge、发布或修改 Ruleset；
- 不读取、迁移、打印或修改凭据和私有认证；
- 不修改 Open Design 私有应用配置；集成配置默认只生成计划、补丁或用户可审阅命令；
- 不把文件存在、Schema 通过、VLM 自评分或合成样例称为真实运行能力；
- 未达到 E3 不得称“可用”，未达到 E4 不得称“已交付”，未达到 E5 不得称“商业验证”。

## 包内容

- 1 份最终总任务书；
- 90 张全新 canonical 任务卡；
- 15 个执行阶段；
- 云端基线、产品宪章、证据与验收合同；
- 机器可读 Schema 与任务包校验器；
- 独立的项目漂移防护合同，覆盖定位、边界、优先级、证据、数据、技术和范围漂移；
- 完整 V3 原始包作为只读来源，保留其 90 张旧任务卡和 199 文件 Overlay，但不再作为执行入口。
