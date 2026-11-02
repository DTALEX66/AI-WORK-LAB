# WORK-LAB 新对话交接摘要（权威压缩版）

**用途**：承接本对话已确认的 WORK-LAB 边界、前后端定位、开源复用、隔离规范、现存问题与下一步。旧文档与当前云端冲突时，以当前可复现云端证据为准。

**项目**：`DTALEX66/WORK-LAB`  
**本机预期根目录**：`D:\All projects\WORK-LAB`  
**既有任务包基线**：`471e90a99b4234e4f5c031c4280c2eba8b065439`；新对话开始先核对 `origin/main` 是否已变化。

## 1. 产品身份与分层

- WORK-LAB 是全局**配置、治理、工作流控制与观测面**，即 Action Authority；不是通用 Agent Runtime、模型网关、知识库或业务项目 CI。
- ArcheAxis 是 Knowledge Authority／未来核心知识 OS；DESIGN-LAB 是设计专业能力层。WORK-LAB 管“可不可以做、由谁做、花多少、是否有回执”，不管理其领域真相。
- Hermes、Codex、DeepSeek Harness、Claude Code、OpenCode 和 Adobe/Figma/Blender/ComfyUI/FFmpeg 都是可替换 Adapter/外部运行时，不能进入领域模型或成为项目身份。
- 不强制所有任务经过 WORK-LAB；跨项目任务才使用其授权、编排和回执能力。

## 2. 前后端最终边界

| 层 | 必须负责 | 严禁负责 |
|---|---|---|
| Control Surface（可写） | 创建/暂停/恢复 WorkUnit，审批高风险动作，策略、预算、权限、Adapter、失败恢复 | 把自己伪装成执行器或知识库 |
| Observer（绝对只读） | Agents、Tasks、Alerts、成本、Attention、Execution Timeline、资源、日志与证据 | 任何写配置/执行操作；把 `UNKNOWN` 显示为健康、成功或 0 |
| 后端控制面 | Task/WorkUnit、Policy/Approval/Budget/Audit、Trace/Token/Cost/Evidence、Sandbox/MCP Gateway 合同 | 复制完整 Agent Runtime、设计工具或知识系统 |
| 外部运行时 | 执行真实代码/工具操作并返回标准 receipt | 自行成为 WORK 的第二真相源 |

前端需要，但应是 **Command Center + 严格只读 Observer**，API-first、无界面也可运行；不是第二个聊天壳或任务执行引擎。

## 3. 数据、目录与沙箱硬约束

- 长期知识、经验、事实归 ArcheAxis；WORK 仅保留任务状态、临时运行日志、缓存、重试、模型引用与审计回执。Secret 只存引用，模型只存 Model Reference。
- WORK 不读取/上传真实用户 Vault、笔记、附件、本机路径或业务项目运行时数据。
- 项目内可创建隔离子目录；运行数据、worktree、cache、logs、artifacts 必须留在项目根 `.project-local/`（或经批准的项目内等价根），不得外溢到其他项目、用户目录或其他盘符。
- `.HERMES` 是工作流软件的本地运行目录，不是业务项目的权威根；若确有历史数据，迁到项目内隔离根并验证后清理旧目录。
- 未知插件/第三方程序默认最小权限、网络隔离，优先 Windows Sandbox/等价环境；MCP 必须有 allowlist、权限与审计。迁移验证完成后，删除旧目录、缓存、重复副本，保持仓库干净。

## 4. 成熟方案优先的复用路线

| 能力 | 首选成熟方案 | WORK 应保留 |
|---|---|---|
| 多模型路由 | LiteLLM；本地模型可用 Ollama、vLLM、LM Studio、llama.cpp | 策略、预算、批准、模型引用和回执，而非再造网关 |
| 任务执行/工作流 | Dagu 等外置 DAG 执行器；各 Harness 适配 | WorkUnit 合同、Gate、失败语义、Receipt |
| 控制台/任务视图 | Mission Control 类成熟控制面，限时资格化 | 权威配置、审批与真值映射 |
| 观测 | OpenTelemetry、TokenTelemetry，必要时 Loki/Prometheus | UNKNOWN 语义、跨运行时关联和审计证据 |
| 供应链/回执 | CloudEvents、in-toto/SLSA | Authority、签名/验证策略、证据链 |
| 沙箱 | OpenSandbox、CubeSandbox、Agent Workspace | 项目级路径、网络、预算和数据隔离策略 |
| 安全/授权 | MCP Firewall、OIDC/OAuth、SPIFFE、Cedar/OpenFGA、Microsoft Agent Governance Toolkit/Nucleus | 最小权限、审批、审计和撤销 |

原则：先整包采用或官方 Adapter，再提炼最小模块；不复制完整上游源码进活跃树，不因“项目热门”堆候选。任何引入必须有版本、许可证、SBOM、真实运行、回滚和退出条件。

## 5. 已审计的关键问题

1. **Observer 假真值**：未知/缺失值仍可能变成 0、干净或成功；必须 fail-visible。
2. **双界面未完全落实**：可写 Control 与严格只读 Observer 的权限与代码边界要拆开。
3. **React 产品线未完整进入 Observer CI**：不能把后端/结构检查绿当成真实前端可运行。
4. **WLR 任务正文与 DSH 注册/权威链曾断裂**：任务包、根规则、Adapter registry 与实际工作流须一致并自动校验。
5. **无限成本策略冲突**：任何“无成本上限/全功率模型”必须改为预算、降级、取消和 fail-closed。
6. **本地 sidecar 可用性问题**：曾出现 offline、LOKI 404；要按端到端启动、重启、断网、失败恢复实测，而不是只看编译。
7. **编译成功不等于语义正确**：已有“注解未解析”、CI 第二写入者、记忆污染风险；配置应单一权威、投影自动生成、写入者可追踪。

## 6. 近期执行顺序

1. 刷新云端 `main`，与上述历史基线做 diff；列出已修复、仍存在、被文档掩盖的项。
2. 建立唯一 Authority/Config/Adapter/Task registry；根规则、任务包、前端、CI 都从该真相源投影。
3. 修 Observer 真值模型与权限：`UNKNOWN/BLOCKED/STALE/FAILED` 不可降级为健康；Observer 无写 API。
4. 把 React Control/Observer 加入真实 CI：构建、路由、权限、断网、错误态、截图级验收。
5. 用外置 Dagu/现有 Harness 跑一条黄金闭环：申请 → 策略/预算审批 → 外部执行 → OTel/CloudEvents → in-toto receipt → Observer 只读展示 → 失败恢复。
6. 再资格化 Mission Control、TokenTelemetry、沙箱与安全组件；删除被上游替代的重复 UI/运行时代码。
7. 完成目录迁移和清理：只在哈希、读回、干净克隆和回滚证明通过后删除旧目录/内容。

## 7. 0.1 usable 验收

- Control Surface 可创建/暂停/恢复任务，并对成本/高风险动作要求审批。
- 同一任务在外部执行器中真实运行，产生输入输出、成本、追踪、版本与签名回执。
- Observer 只读展示真实状态；断链时明确 `UNKNOWN/STALE`，没有伪 0 或伪成功。
- 路径、网络、密钥和客户数据不越出项目边界；从空环境可按锁定配置恢复。
- React 前端和 API 的真实链路进入 CI；失败路径与一次人工拒绝/恢复均有证据。

## 8. 禁回归清单

- 不新造通用 Agent Runtime、完整模型网关、知识库或业务设计工具。
- 不把 Hermes/Codex/DSH 等写进领域模型；它们可替换。
- 不把 Observer 变成可写控制面，不把 UNKNOWN 伪装成正常。
- 不将全局配置或任务缓存散落在 `.HERMES`、外盘或其他项目。
- 不以“编译通过/报告说已完成”取代端到端运行、读回和用户验收。

## 8.1 已废止或被纠偏的历史方向

这些不是待选方案；它们出现过，因此需在新对话显式排除：

- **“WORK-LAB 只是监控看板”**：错误。它需要可写治理控制面，但 Observer 仍必须绝对只读。
- **“WORK-LAB 自己再造一个万能 Agent/视觉/模型 Runtime”**：错误。执行器、模型服务、创作软件均为可替换外部 Adapter。
- **“所有项目、所有任务都必须经 WORK”**：错误。WORK 是跨项目或需治理任务的 Action Authority，不劫持业务闭环。
- **“配置写在各 Adapter、各任务包或 `.HERMES` 中也可以”**：错误。必须由一个 canonical registry 驱动投影，运行软件目录不是真相源。
- **“未知就是 0、默认健康、没有成本”**：错误。未知、过期、阻塞、失败必须在 UI/API/日志同义呈现。
- **“一次静态检查或一次成功启动等于已接入”**：错误。成熟度应至少区分候选、登记、原型、集成、实测、发布；必须有运行读回和失败证据。
- **“为了快速迭代先把上游仓库整包复制进来”**：错误。只可整包外置采用、官方 Adapter 或最小吸收；副本必须有锁版本、许可证、SBOM、退回路径。

## 8.2 跨项目接口与数据所有权

| 数据/动作 | Owner / 真相源 | WORK-LAB 可做 | WORK-LAB 不可做 |
|---|---|---|---|
| 用户知识、原件、来源、学习证据 | ArcheAxis | 请求已批准的最小引用/回执 | 拷贝或吸收用户知识库、原件和私有附件 |
| 设计 Brief、DesignIR、Rubric、视觉审核、交付资产 | DESIGN-LAB | 发令、审批、预算、接收匿名化回执 | 定义设计质量真相、存客户素材或替代人工 Jury |
| WorkUnit、权限、策略、成本、运行日志、短期缓存 | WORK-LAB | 创建、编排、审计、恢复、过期清理 | 把短期运行缓存伪装成长期知识 |
| 模型、Agent、宿主软件 | 外部运行时/官方产品 | 注册版本、能力、权限和调用 receipt | 锁死某一个软件/模型，或将模型权重/密钥混入 Git |

建议的最小跨项目链路是：`WORK 发令与审批 → DESIGN 或 ArcheAxis 在自身边界执行 → 返回不可抵赖 Receipt → WORK 只读观测与治理归档`。原始资产/私有内容默认不跨边界。

## 8.3 目标目录语义（迁移后的规范）

```text
WORK-LAB/
├─ 00-governance/       # authority、policy、approval、预算、审计合同
├─ 10-workflow/         # WorkUnit、编排合同、外部执行器 Adapter
├─ 30-observer/         # 严格只读展示与观测投影
├─ 40-knowledge/        # 仅目录/引用，不保存 ArcheAxis 的知识真相
├─ 50-taskpacks/        # 版本化、可执行、可追踪任务包
├─ apps/control-surface/ # 可写前端（若存在）
├─ integrations/        # Harness、MCP、OTel、模型/工具官方 Adapter
├─ vendor/              # source lock、许可证、SBOM；非完整第三方副本
├─ tests/               # 合同、CI、端到端、故障注入
└─ .project-local/      # ignored：runs、cache、logs、worktrees、artifacts
```

历史目录名可以存在于迁移清单中，但不得被误认为软件根目录或权威配置根。若目录迁移产生旧内容，必须按“冻结→哈希/来源→迁移→引用更新→空环境验证→清理→干净克隆复验”的顺序处理。

## 9. 新对话启动指令

```text
请以《WORK-LAB 新对话交接摘要（2026-09-03）》为约束，先只读核对 DTALEX66/WORK-LAB 当前 origin/main 与历史基线 471e90a99b4234e4f5c031c4280c2eba8b065439 的差异。WORK-LAB 是 Action Authority 和全局控制/观测面，不是 Agent Runtime、模型网关或知识库。先审计前端的可写 Control Surface 与只读 Observer，重点检查 UNKNOWN 假真值、React CI、任务包/DSH/registry 权威断链、成本上限、sidecar offline/LOKI 404 与运行目录外溢。对每个问题先调研成熟开源或商用方案，优先外置采用/官方 Adapter，禁止默认自研。目标是完成一条真实黄金闭环并给出证据、差异、选型和任务 DAG；未经我授权不要修改或推送仓库。
```

## 10. 应优先读取的历史材料

1. `WORK-LAB完整项目对话与时间线汇报.md`
2. `WORK-LAB-FINAL-HERMES-TASKPACK.md`（`WORK-LAB-FINAL-CONSOLIDATED`）
3. `WORK-LAB-STAGE-2-SELECTIVE-ABSORPTION-DELTA-HERMES-TASKPACK.md`（`WORK-LAB-STAGE-2-ABSORPTION-INTEROP` / `...DELTA-22`）
4. 当前仓库的根规则、Authority/Adapter registry、Observer、React CI 与任务包正文。
