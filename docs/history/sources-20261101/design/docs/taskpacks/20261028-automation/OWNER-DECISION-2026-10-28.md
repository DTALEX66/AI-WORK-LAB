# OWNER DECISION — 2026-10-28 外部软件自动化解冻、移植包吸收、体积清理与分支收口

- 决策 ID：`DL-OWNER-DECISION-20261028-AUTOMATION-R1`
- 状态：`ADOPTED`
- 适用仓库：`D:/All projects/DESIGN-LAB`（仅 DESIGN-LAB；不写入 WORK-LAB / AAOS）
- 上位权威：`/AUTHORITY.md`（`DL-AUTHORITY-2026-09-18-R2`）§17 采纳条款
- 前手决定：`DL-OWNER-DECISION-20261023-DESKTOP-KB`（当前派工入口 `DL-TP-20261023-DESKTOP-KB-R1`）、
  `DL-OWNER-DECISION-20261020-UNFREEZE`、`DL-OWNER-DECISION-20261019-DIRECTION`
- 来源：owner 在本项目会话内直接指令 + owner 随消息投递的目录
  `D:/All projects/Record/新建文件夹`（9 个文件，非 ZIP 投递，无随包签名）；
  该目录的逐文件与逐成员摘要由 `docs/history/record-archive-2026-10-28-design-automation/SOURCE-MANIFEST.json`
  承载。**不得**把本文件的口头指令伪装成外部包哈希。

## Owner 原话（逐字）

> 取消冻结的自动化任务  （D:\All projects\Record\新建文件夹     把这里的内容吃透）

> 前端也同步上去自动化的菜单导航等

> 并行执行 项目体积清理与规范化  执行合并迁移清理等相关执行，任何过时的陈旧的冗余的，该归档的归档 包括目录子文件夹等

选项式补充（owner 在本会话的选择面板里给出，逐字）：

> 清理授权范围：**只清派生物** + **再加：仓库内历史归档合并** + **再加：PR #277 合并 + 分支收口**

> 包怎么进项目：**全部吸收融入本项目  和原先冻结的自动化任务进行合并**

## 效力与解释

1. **`外部软件自动化` 从冻结清单移出，进入可派工**。本决定取代 `AUTHORITY.md` 2026-10-23 采纳条款第 4 条、
   `authority-index.json` `desktopKbAdoption.stillFrozen` 中的 `EXTERNAL_SOFTWARE_AUTOMATION`，
   以及 `AGENTS.md` 同名列举。它与 2026-10-19 已确立的工具策略不冲突——`官方 API/SDK → 原生插件 → MCP →
   脚本/CLI → 受控 UI 自动化` 本来就是本项目的分层接入面，被冻的是"做"，不是"写进规划"。
2. **解冻的是能力类，不是逐次宿主操作授权**。"取消冻结"不等于任何会话可自主启动 Photoshop / Illustrator /
   SketchUp / Revit / 3ds Max / Blender / Rhino / InDesign / AutoCAD 或读取桌面。每一次真启动宿主、
   每一次 `tools/call` 改原生文档，仍按 `AGENTS.md` 的 Human Gate 与本文件第 3、4 条判断。
   默认面必须是"未探测"（`NOT_PROBED`），不是"可用"。
3. **`windows` 连接器不在本轮吸收的可执行面里**。包内 `config/connections.json` 的第 11 个连接器
   `windows`（`adapters/windows_entry.py`）是**桌面 UI 自动化**——读屏幕、动鼠标键盘那一档。
   本决定只把它登记为已识别素材，不启用、不接入、不派工；解除要 owner 另给一句明确授权。
4. **权利未判定的素材只登记不启用**。包内 `vendor/Settings/Skills/ppt-master/templates/brands/` 是
   **21 个真实公司名模板**（McKinsey / Google / 中国电信 等），`NOTICE.md` 自己写明
   "不把某个组件的 MIT 声明推广为全部 JZXZ、全部资源或商业软件的统一许可"；整套材料源自商业软件
   建筑学长 JZXZ 1.1.27（`D:/jzxz`），含反编译 `.il.txt` 证据，上游未授予再分发许可。
   因此这些成员按 **inert source blobs** 逐字节入库登记，不进入根指令、prompt、工具发现或能力计数，
   也不作为产品能力对外声明。逐组件许可判定属 Rights gate，由 owner 或其后授权的人裁定。
5. **第三方指令体一律惰性**。包内 21 份 `SKILL.md`、`interior-3d-web/开始生成.md`、
   `ppt-master/scripts/prompt_audit.py`、`PhotoshopMCP/server/dist/core/prompt-registry.js` 等
   是给别的 Agent 读的正文；其中还有 `Install: pip install requests beautifulsoup4`、
   `npm install -g docx` 这类安装/联网字样。DESIGN-LAB 不自动执行它们，
   不因"包里有 SKILL"把它算进自己的技能数或能力面。
6. **吸收的落地形状（这是工程约束，不是偏好）**。"全部吸收融入本项目"按本仓既有分层实现：
   包自带的 `gateway.mjs` / `runtime/` / `config/connections.json` 不是 DESIGN-LAB 的 runtime，
   不得成为第二执行面；吸收＝在本项目内建立自己的合同层——`integrations/` 下的版本化 adapter 登记、
   `src/design_lab/automation/` 的只读投影与有界桥接客户端、`Route(...)` + schema + 账本行、
   以及 `apps/workbench/` 的真实路由。界面必须映射真实 API，**不得以效果图宣称接通**。
7. **证据等级上限本轮是 E1/E2**。包自证的最诚实读数是"握手过、没动过宿主"：
   9 个 stdio 桥接器可列工具（SketchUp 8 / AutoCAD 7 / Rhino 38 / Blender 28 / 3ds Max 151 /
   InDesign 27 / Illustrator 66 / Photoshop 80 / Revit 138），
   `evidence/release-check-20261028T094750801Z/bridge-catalogs.json` 逐条 `nativeToolCalled:false`，
   且 `evidence/relocation.json` 写 `"physicalSecondComputerTested": false`。
   `tools/list._meta.connectorStatus` 只由 `gateway.mjs:21` 的 try/catch 产出
   `MCP_READY` / `UNAVAILABLE` 两值，含义是"握手+列工具成功"，**不等于宿主可用**；
   ` Grasshopper` 的 URL 本轮未连通，`windows` 只查了依赖可发现性。
   不得把 543 条工具数读成能力数，也不得据此声明真实宿主 E3、真人 E4 或 release。
8. **体积清理与规范化的授权范围（三层，逐层判断）**：
   ① 派生物（`.project-local/` gitignored 运行根内的缓存、临时目录、残留 worktree、日志）——
   删除前必须逐目录证明"要么被重跑再生、要么被跟踪清单按摘要绑住"；
   `projects/` 状态数据、`record-archive-2026-10-23`、`record-archive-2026-10-27` 这类
   被受跟踪 manifest 点名要能按摘要补回的原件**不删**。
   ② 仓库内历史归档合并（含目录与子文件夹）——冻结原件**原字节不动**，只换指针与取代关系，
   并按 2026-10-27 钉下的收口顺序重绑登记件、权威链与现行投影。
   ③ PR #277 合并 + 分支收口——本文件所在工作先由 CI 在承载字段的 head 上读回 success 再合；
   远端分支删除按 owner 本条授权执行。
9. **不变项（一条没动）**：手机端仍是排除项（「再说一遍 不做手机端 只做桌面端」）；
   三方素材与字库仍在项目范围外；E 盘不动；不部署模型、不自行下载权重、不宣称推理已验证；
   `UNKNOWN` 不写成合格，云端选项必须写明哪些数据离开本机；编号仍由用户填写或显式选 `UNUSED`；
   验收与签字仍只接受具名真人；候选导出仍是读回不是发送；AAOS 仍只是未来合同；
   release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 继续冻结；
   旧 34 项 `currentExecution` 仍 `FROZEN_DEFERRED`（解冻任何一项仍需 owner 新的明确授权）；
   `DESIGN.md` 在 owner 真实测试前不进入已批准状态；
   不得靠改断言、删接口、硬改能力标记或把失败改成演示成功来通过；`.codebuddy/` 与 `.cursor/` 永不暂存。

## 本决定没有做的事

- 没有启用 `windows` 桌面 UI 自动化连接器，没有启动任何专业宿主，没有调用任何 `tools/call`。
- 没有判定 21 个品牌模板与各上游组件的许可归属；只做了逐字节登记。
- 没有把包内任何 `SKILL.md` / prompt / install 文字接入本项目的指令面或能力计数。
- 没有声称包可在"另一台电脑"复现：该断言由 `physicalSecondComputerTested:false` 直接反驳。
