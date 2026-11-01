# OWNER 裁决记录 2026-10-23 — 前端 UI 新规划入派工、方案包归档、权威与规划覆盖替换

来源种类：会话内指令（owner 在 Qoder Desktop 会话中直接下达，并随附两份 Record 投递材料）。
无外部任务包下发编号，无独立 ZIP 之外的源哈希；源哈希见 `SOURCE-MANIFEST.json`，本节不虚构哈希。

## 1. owner 原话（逐字）

> 读取分析，按照这个执行（前端UI有新规划），并且归档到统一项目里，更新覆盖替换到权威和规划里

随附投递（`D:\All projects\Record`，2026-10-23 18:57 观察）：

- `DESIGN-LAB_今日完整需求与可行性方案_20261023.html` — 59,898 B，`614b4a7c15bfb6497823aa5d2f818a651b96b84d5bfbe2394ecee55143e893da`
- `DESIGN-LAB_今日完整方案与STITCH交接包_20261023.zip` — 70,319 B，`9fadae0ae12712c31c41b7e214e549e1a6b32e54ee4eb9f0fde1cf749898aff7`

> 先分析拆解，加入到优先到任务台账里，梳理本对话所有内容，给我完整提示词，我去开启新会话

## 2. 这批指令改变了什么

1. **前端 UI 进入当前派工面。** 之前「只归档整理、不实施产品功能」与后端批次 I 的「全程不动前端一行」在桌面 UI 这一段上失效；本仓库唯一可变状态源（`design-lab/config/task-ledger-r3.json` 的 `currentExecution`）新增 16 项派工（`DL-KB-01`…`DL-KB-16`），优先级即包内第 17 节的阶段序：知识管理与中文检索 → 中立方案与目标档案/导出 → 一个方案助手模型的真实接入 → 内容模板与反馈。
2. **`DL-TP-20261019-DIRECTION-R1` 不再是唯一派工入口**，被 `DL-TP-20261023-DESKTOP-KB-R1` 取代；方向包原字节保留，定态降为 `SUPERSEDED / LINEAGE`（前继血统）。
3. **归档到统一项目**：17 名成员逐字节入仓到 `docs/taskpacks/20261023-ui-kb/source/`，`SOURCE-MANIFEST.json` 登记逐成员 sha256/crc32/bytes/state/disposition；`docs/history/record-archive-2026-10-23/ARCHIVE-MANIFEST.json` 登记卷宗来源、别名与去重（外部 HTML 与包内同名成员同哈希，只留一份规范副本；ZIP 原件留 `.project-local`，不随 Git 克隆）；`docs/RECORD-ARCHIVE-INDEX.md` 追加 2026-10-23 日期节。既有普查计数不改写、不并入。
4. **权威与规划覆盖替换**：`AUTHORITY.md` 增加 2026-10-23 采纳块，`.project/governance/authority-index.json` 的 `current`／`taskpackClassificationRule`／新采纳键指向新包，`AGENTS.md` 与 `docs/current/PRODUCT_DEFINITION.md`、`docs/current/NEXT-AGENT-PROMPT.md` 的当前任务包指针同步改；因两份权威面字节变化，`R2_RELEASE_HASHES` 对这两份重钉并在 `docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json` 追加 revision。

## 3. 这批指令没有改变什么（逐条仍然成立）

- 原 34 项 `currentExecution` 父/子任务全部保持 `FROZEN_DEFERRED`。新增派工**不是**对这 34 项的解冻；要解冻任何一项需要 owner 新的明确授权。
- 手机端仍是排除项；`currentExecution.mobile` 仍是 schema `const FROZEN_DEFERRED`（改词需要 owner 授权并改 schema，本轮都不动）。
- release、安装态分发、真实宿主 E3、真人 E4、ComfyUI、MiniMax H3 继续冻结。
- 模型不锁死的规则不变：默认 fail-closed；显式选择只是被记录；`UNKNOWN` 不写成合格；不宣称推理已验证；云端必须披露离开本机的数据。本轮**不部署模型、不自行下载权重**（包内第 11 节把这件事排为第三阶段，且 `10_本地CODEX接续提示词.txt` 明写「模型部署不自行进行」）。
- 编号规则不变：外部 `source.job_id`/`operation_id` 由界面填写或显式选择「不使用」（`UNUSED`）；内部对象 ID 可由系统铸造，但不得当作外部来源证据。
- 字体库与第三方素材权利判定仍在项目范围外；不默认外传客户素材；E 盘受保护。
- 签字、审核、验收仍只接受具名真人；`KnowledgeCandidate` 导出仍是读回，不是发送，`outbound` 仍是未连接。
- AAOS 只保留标准、通用、版本化的公共合同，不是依赖、不是门、不是当前缺口。

## 4. 与投递包自身声明的一致性

包内 `00_先读这里.md` 与 `02_完整产品方案.md` §19 自己写明：这是规划与交接包，不代表已实现、已测试；未改云端/本地产品仓库，未部署模型，未操作外部制作软件。本裁决按此性质接收：**采纳的是范围、优先级与验收口径，不是完成状态**。包内 `13_包内一致性核对.json` 的 `requirementCount`/`sourceCount` 等是作者自查，不进本仓库的证据面。

包内 `09_DESIGN.md` 与 `08_STITCH完整提示词.txt` 的界面规则被采纳为**待实机验证的设计约束**（三主入口、单主动作、玻璃只给导航与临时面板、正文 14–16px、系统字体、无持续动效、无手机端）。owner 2026-10-20 已裁定 `DESIGN.md` 在其真实测试前不进入已批准状态，因此这些约束的效力是「按此实施」，不是「已批准」。既有珍珠白／炭黑配色与 `--border-strong` 等已实测定过的值不因新包改写；配色归属仍挂起。

## 5. 落仓时观察到的基线

`docs/taskpacks/20261023-ui-kb/SOURCE-MANIFEST.json` 与 `docs/history/record-archive-2026-10-23/ARCHIVE-MANIFEST.json` 登记的是落仓时 `observed_head`（`efa5a8af…`，批次 I 的 CI 已验证枚）；包内作者基线 `2d6ede51cd0f49e9b99c27f09924a0db29843b89` 保留为作者观察时点，不冒充当前值。当前真实 SHA 一律 `git rev-parse HEAD` 自读。
