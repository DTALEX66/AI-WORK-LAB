# DESIGN-LAB 全历史与当前状态审计

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。

## 结论与审计边界

正式产品应继续是**面向职业视觉设计的 AI 原生、平台中立、宿主原生设计智能与生产能力层**。保留 Lite 工作台、软件 Launcher 和设计适配器诊断，并不要求转型成 Agent OS。最短可用闭环是“真实 Brief → 获授权参考 → Direction / Design System → 可修改 Design IR → Adobe 宿主生成及局部修改 → readback → Human Jury / rights / preflight → 可编辑交付及重新打开验证”。

本次覆盖了可访问证据，但不能宣布“完整原始历史已恢复”。Library 枚举 3,917 项、20 页至游标结束；manifest 全部 536 行保留，其中 **522 行原始 SHA256 匹配、10 行未恢复、4 行占位**。522 是记录数，不能当作独立文档数。manifest 包含 300 个非零内容哈希，另有零哈希占位组。全部 canonical_record 关系校验异常：0。可达 main 历史检索了 536 个提交及 12,955 个 Git 对象，仍未找到缺失原件；这不代表遍历了账号所有私有聊天或不可达 Git 对象。

最重要缺口是 `DESIGN-LAB完整项目对话与时间线汇报.md`（预期 8,961,542 bytes）。229,424 行及 16 段对话属于旧材料中的报告值，本轮未读取原件，不能将摘要冒充逐行恢复。另两项目完整对话也未恢复。指定两份 9/28 启动/最终执行文档的 txt/docx 未找到；实际读取的是 `DESIGNLAB_商业级前端与能力闭环_后续任务包_20260928` 及其四份正文，不能宣称二者完全等价。

## LIVE 与权威

- LIVE main 已在本轮开始与收尾重新读取，均为 `010f6a57610214fa41651861e00319f88a2f49a4`；tree `3cb2fd27344e06b3758d37230c3611f31efc197d`，递归条目 3,386，非截断；当前只有 main，open PR 为 0。
- branch 返回 protected=true、9 个 required checks；完整 protection 管理端点返回 403，因此管理员审查人数、豁免等配置仍属 UNKNOWN，不可写成“无保护”。
- 当前 exact-SHA Canonical Verify run [36501310080](https://github.com/DTALEX66/DESIGN-LAB/actions/runs/36501310080) 的 10 个 job 均 success。两个 artifacts 元数据可见；未直接下载并验算 artifact 字节。CI success 支撑覆盖范围内 E2，不支撑 Adobe E3/E4。
- Authority 为 `DL-AUTHORITY-2026-09-18-R2`，统一任务入口为 9/18 convergence TaskPack；`design-lab/config/task-ledger-r3.json` 是唯一编辑源。文件名 r3、schema R5 与历史沿革并存，不应据名称新建账本。
- current progress 为 28 项 PARTIAL，fresh=false，绑定旧 WORKTREE / dirty subject。不能因报告最近生成就宣称当前 main E5。

## 最关键的十项裁决

| 问题 | 裁决 | 证据 / 限制 |
| --- | --- | --- |
| 旧 OPEN-DESIGN 能力还要保留什么 | Brief、Design IR、Domain/Method Pack、Jury、visual DNA、生产预检、可编辑交付、rights/provenance、回读与回滚全部保留 | 不保留 Open Design-first 的核心依赖 |
| 视觉质量体系是否遗漏 | 文件层面大量继承；运行层面未完整闭环 | V2.1 120 文件：87 字节一致、33 同名演进候选；仍缺真实成品独立验收 |
| UI/VI 怎么继承 | 保存旧稿与变体，提炼 token / component / motion / assets 清单，再选择当前有效版本 | 不能让每个旧包同时定义当前视觉基线 |
| Lite 是什么 | 正式产品的轻量入口和同一数据模型上的界面模式 | 不是第二产品、第二运行时、第二账本 |
| Launcher/MCP 能多深 | 启动用户已配置设计宿主、显示设计能力、健康检查、设计工具调用诊断 | 全局客户端/代理配置、跨项目调度归 WORK-LAB |
| 商业个人 UI 缺什么 | 完整状态反馈、真实 bundle 列表、token 版本编辑、宿主状态、质量/rights工作流、键盘/IME/可访问性、安装后端到端闭环 | 已有项目/Brief/资产/方向/系统绑定及任务操作，不能说前端全是假壳 |
| OSS 应如何吸收 | 优先可访问性验证、tokens 转换、资产与预览 primitives；对 SWC/Web Awesome 做当前 CSP/打包兼容比较 | 不能仅凭 CSS class 存在认定商业成熟，也不为换库而重写框架 |
| 宿主优先级 | Photoshop / Illustrator 优先，Figma/Penpot 次之，Blender/视频随后 | 用户已有 Adobe 环境；M1 的双宿主门槛不可静默降成单宿主 |
| MiniMax/H3/Comfy | MiniMax Design 外部客户端；H3 模型；官方 Comfy 插件是工具适配；Comfy 是可选生成 sidecar | 本地模型文件存在不代表可运行；H3 hosted IR 与本地 Base 不等价 |
| 最短闭环 | 一个真实项目、两轮可回读修改、rights+human gate、可编辑包重新打开 | 不以截图或模型自评代替专业接受 |

## 源码与运行分开

`apps/workbench/` strict TypeScript + Vite / pnpm 与 Python 后端已有真实增量实现。Research、design-domains、collaboration 页面明确尚未开放完整数据闭环；已有 API 并非全 mock。`native_assets.py::Bundles` 查询已实现并测试，但列表 HTTP 路由及 UI 仍未接入；bundle 创建与 content 下载路由已经存在。查询数据库应使用 `asset_kind='other' AND asset_id LIKE 'bundle-%'`，响应语义可为 `design-bundle`，不得混淆。

当前交付元数据仍包含 rights/quality `NOT_REVIEWED`、link relocation `NOT_VERIFIED`、font inventory `REQUESTED_ONLY` 等，因此“成功导出 zip”不是生产验收。DTCG 转换器已存在，后续应补持久化、版本差异、发布/回滚 UI，而非重复建立 token 格式。

本轮本地只读验证命令 `scripts/generate_current_reports.py --check` 被缺少 `jsonschema` 阻塞（系统与主运行时均如此）；没有安装依赖、没有据此判定仓库 gate 失败。未启动用户 Windows 软件、未安装模型、未修改素材或仓库。

## 已证实的文档漂移

1. 下位 `EVIDENCE_POLICY.md` 的 E4/E5 描述与顶层 Authority 不一致，必须以顶层定义为准，后续修复下位文档。
2. `SOURCE_REGISTRY.md` 旧计数 active=0，与 JSON 6 项不一致；这 6 项 integration.target 均仍指向不存在的 `design-lab/knowledge/...` 旧路径。不得把路径迁移等同内容丢失，也不得把 active 字样等同已可用。
3. 历史 Comfy 受控/实机记录与当前 supported=false 分属不同时间和范围。界面必须同时展示历史最高等级、当前资格和证据有效性。
4. Roadmap 大数量能力叙述与当前 capability-index 五条记录不是同一计数单位，不能据此宣称数千个生产能力。

## 后续执行原则

本包 13 号文件是候选任务包，先映射现有 DL-R5 任务，不自动取代 Authority。历史缺口恢复与前端闭环可以作为后续独立工作，但在本轮只读约束下均未实施。真正 Owner Decision 包括视觉基线、架构迁移、受限许可接受和实机专业验收；既有 Authority 已明确的单账本和三项目边界不应反复请求决定。

主要证据：[AUTHORITY.md](https://github.com/DTALEX66/DESIGN-LAB/blob/010f6a57610214fa41651861e00319f88a2f49a4/AUTHORITY.md)；[src/design_lab/http_service.py](https://github.com/DTALEX66/DESIGN-LAB/blob/010f6a57610214fa41651861e00319f88a2f49a4/src/design_lab/http_service.py)；[src/design_lab/native_assets.py](https://github.com/DTALEX66/DESIGN-LAB/blob/010f6a57610214fa41651861e00319f88a2f49a4/src/design_lab/native_assets.py)；[src/design_lab/native_bundles.py](https://github.com/DTALEX66/DESIGN-LAB/blob/010f6a57610214fa41651861e00319f88a2f49a4/src/design_lab/native_bundles.py)；[reports/current/TASK_PROGRESS.json](https://github.com/DTALEX66/DESIGN-LAB/blob/010f6a57610214fa41651861e00319f88a2f49a4/reports/current/TASK_PROGRESS.json)。完整导航见 README，缺失清单见 Source Registry。
