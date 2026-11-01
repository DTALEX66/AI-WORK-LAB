# DESIGN-LAB 新执行任务包

**包 ID：** `DL-TP-20260907-R4.1`  
**冻结基线：** `DTALEX66/DESIGN-LAB@c4dccd58331bc4561eb89265283d924b7630d113`  
**范围：** 个人、非商业研究；独立 DESIGN-LAB 工作台；优先 Illustrator / Photoshop 可编辑复刻。  
**状态：** `PLAN_DELIVERED — 未实施`。R4.1 已审计并纳入“独立增强任务包”；它不是已实现声明。

这是 2026-09-07 云端复审后的替代执行包。它不撤销已经合并的 PR #115 修复，也不把结构测试通过冒充为用户可用。其首个可用目标（M1）是：

> 在 DESIGN-LAB 界面导入一张参考图，选择 AI 或 PSD，获得真实原生可编辑工程；完成至少两次对象局部修改、保存、关闭重开、结构读回和预览对比。

不等待全仓改语言、H3、Premiere、Blender、音频或全面历史恢复。它们有独立任务，不能阻塞 M1。

## 本包解决什么

1. 让状态、任务、证据和当前提交只剩一个权威来源，防止不同 Agent / 模型的结论漂移。
2. 完成 `.hermes` 到项目运行根及作品库的真实迁移，而不是只改部分代码或文档。
3. 修复已经复现的 Operation、Attempt、资产版本、Profile、模型就绪和 Comfy 回执语义问题。
4. 用 Python 服务、TypeScript 工作台、宿主 JavaScript / JSX 形成产品链路。
5. 将 ComfyUI（及受控的官方本地 Comfy MCP）纳入 DESIGN-LAB：可复现、可取消、可回读，但不重建 ComfyUI。
6. 从静态适配器推进到 Illustrator 与 Photoshop 的真实原生工程操作；把 UI 自动化限定为可审计的后备层。

## 阅读顺序

- `01-AUDIT-BASELINE.md`：当前真实状态和发现。
- `02-EXECUTION-PLAN.md`：任务、依赖、验收与回退。
- `03-DRIFT-PROTOCOL.md`：多模型执行而不漂移的强制规则。
- `04-ENHANCEMENT-INTAKE-AUDIT.md`：本次增强包的逐条采纳、延后与安全收敛。
- `tasks.json`：机器可读任务图。
- `evidence/`：本次冻结、可复现缺陷及研究来源记录。

## 不可突破的边界

- 不访问、不写入 E 盘；除非用户在当前任务中明确授权具体路径和动作。
- 不把 WORK-LAB、ArcheAxis、OpenDesign、Hermes 或 DSH 设为 DESIGN-LAB 启动必需依赖。
- 不把模型、缓存、生成物、用户工程或凭据提交 Git；不覆盖用户现有 Adobe 文件。
- 本地 ComfyUI/MCP 默认只连接任务中声明的实例；模型下载、云端付费、批量任务和外部传输需要已记录的明确作用域授权，不能由普通生成任务隐式触发。
- H3 在适用地域、许可版本和本机可行性未逐项核实前保持不可执行；个人非商业用途不自动解除其他条件。
- 不用 GUI 自动化替代可用的宿主 DOM / 脚本接口；不把截图、Schema、CI 绿或 NOT_EXECUTED 当成实机完成。

## 过渡关系

此包取代执行顺序，不删除历史：

- `DL-TP-20260904-STANDALONE-FIRST`：保留原始 58 项任务与历史映射。
- `DL-TP-MULTIMODAL-20260905`：保留 T01—T18 的范围。
- `DL-TP-20260906-R3`：其 24 项修复与产品任务被本包重排、收敛。

所有旧记录必须通过 `old-new-crosswalk.csv` 追到本包任务；不得覆盖原文或把未实机的旧证据改写成当前成功。
