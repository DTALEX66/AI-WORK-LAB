# DESIGN-LAB 后续执行任务包 V1.1

项目：`DTALEX66/DESIGN-LAB`  
本地：`D:\\All projects\\DESIGN-LAB`  
适用：DeepSeek Harness、Hermes、Codex  
云端审计基线：`main@a6fdc5e`；执行前必须重新获取 `origin/main`。

## 一、不可变基线

DESIGN-LAB 是职业视觉设计的设计智能与生产能力层，负责专业判断、Design IR、视觉质量、生产预检、可编辑交付及工具计划。

它不是第二套设计软件、画布编辑器、Agent Runtime、模型网关、通用知识 OS、素材站或脚本仓。

ArcheAxis-Knowledge-OS 未完成前，设计知识暂留 DESIGN-LAB；原始大资料留在 `D:\\All projects\\Design assets`。不得迁移、删除或清空知识，仅可建立未来迁移清单和兼容契约。

Open Design、Hermes、Codex、DSH、OpenHuman 均为可选入口；Adobe、Figma、Blender、ComfyUI、FFmpeg、Eagle 均为可替换执行适配对象。不得设置默认宿主。

MiniGame 只保留为游戏视觉 Fixture，不恢复独立产品。

## 二、执行纪律

1. 先执行 `git fetch --prune`、记录 SHA、检查工作树；有未识别用户变更即停。
2. 只读审计和本地修改可执行；commit、push、PR、merge、分支删除、历史重写、真实用户文件写入均须单独批准。
3. 不读取凭据正文、不扩大可写根、不扫描盘符根、不触碰 `E:`。
4. `Design assets` 默认只读，只对用户指定子目录摄取；不提交绝对路径、客户隐私、PSD/AI/INDD/视频/字体原件。
5. 规划、文件存在、安装成功、握手和工具枚举都不是生产完成。
6. 每任务提交：taskId、状态、范围、修改文件、验证命令、证据、exact SHA、阻塞项、回滚。

状态：`PASS / PARTIAL / FAIL / BLOCKED / DEFERRED / NOT_EXECUTED`。

证据：

| 级别 | 定义 |
|---|---|
| E0 | 声明、设计或注册 |
| E1 | 结构、握手、能力枚举 |
| E2 | 隔离任务成功且存在可核查产物 |
| E3 | 真实运行任务、产物 readback、可重复证据；若任务要求可编辑源文件，必须重开并验证可编辑性 |
| E4 | exact-SHA 独立复审、发布 attestation |
| E5 | 多环境/长期/真实用户验证 |

## 三、P0：当前事实与身份收敛

### DL-GOV-100 云端事实重建

生成 `CLOUD_BASELINE.json/.md`：main SHA、分支保护、PR/Issue、工作流、体积、追踪文件、生成时间。云端状态与本地工作树状态彻底分开。

### DL-GOV-110 退出旧 Open Design 中心化

- `PRODUCT_DEFINITION.md` 是唯一产品定义。
- 将冲突的 `PROJECT_DEFINITION.md`、旧 Open Design enhancement 文档转入 history。
- README、Architecture、Boundary、Manifest、Roadmap、CI 中移除 reference host/default host/主入口语义。
- Open Design 只作为 `adapters/hosts/open-design` 的兼容对象。

### DL-GOV-120 Current 报告治理

将三份旧 handoff 和过期 FINAL 归档；建立 `CURRENT_REPORT_INDEX.json`。

只允许以下报告为 current：Cloud Baseline、Project Status、Adapter Reconciliation、Knowledge Inventory、Domain Readiness、Release Readiness。每份必须有 subject SHA 和 fresh/stale 标记。

### DL-GOV-130 反漂移验证器

新增 `verify_project_drift.py`，阻断：

- 旧产品身份与默认宿主；
- 第二 Agent Runtime/模型网关/通用数据库/画布编辑器；
- MiniGame 产品化；
- 工具脚本进入 `knowledge/`；
- E0/E1 宣称 stable、operable、production-ready；
- current 报告 SHA 不一致；
- 未有黄金纵切证据却新增大量 Adapter。

### DL-GOV-140 治理收尾

管理员开启 main branch protection、required checks、禁止直接强推；建立任务账本；仅报告分支清理候选，不删除分支；建立 224 MiB 预警、256 MiB 上限。

P0 Gate：身份扫描、报告新鲜度、Canonical 验证、drift gate 全部 PASS。

## 四、P1：临时知识治理与多格式资料转化

### DL-KNW-100 临时知识目录

建立：

```text
design-lab/knowledge/
  staging/{source-records,extracted,normalized,candidates,reviewed,mappings,migration-manifests}
  quarantine/
  projections/
  registries/
```

每条记录必须有 `authorityStatus=temporary-design-lab`、`targetAuthority=ArcheAxis-Knowledge-OS`、`migrationStatus=deferred`、来源、许可、hash、版本、review 状态与编译目标。

### DL-KNW-110 多格式转换管线

对用户指定的外置子目录，建立 dry-run-first 转换器：

| 输入 | 结构化输出 |
|---|---|
| PDF/网页/文档 | 文本、章节、引用、表格、来源与许可证 |
| 图片/截图 | OCR、版式、颜色、字体候选、构图/层级、Reference DNA |
| 视频 | 转录、镜头、关键帧、节奏、字幕、视觉方法卡 |
| 音频 | 转录、时间轴、音效/音乐标签、许可状态 |
| PSD/AI/INDD/SVG | 元数据、图层/对象树、颜色、字体、链接资产、可编辑语义 |
| Blender/3D | 场景、对象、材质、灯光、贴图、单位、导出格式 |
| 字体/素材包 | 文件 hash、许可证、授权范围、禁止用途 |

原件和本地缓存不进 Git；Git 仅保留 SourceRecord、RightsRecord、ExtractionJob、CandidateKnowledge、摘要、映射与编译结果。

### DL-KNW-120 生命周期与调用边界

```text
registered → extracted → normalized → candidate → reviewed → compiled
                                      ↘ rejected / quarantined
```

运行时只能调用 reviewed、projection、Domain Pack 和已验证规则；candidate/quarantine 禁止进入生产任务。

### DL-KNW-130 现有资产重分类

逐文件将现有知识分为：事实/方法知识、编译规则、vendored source、tool asset、projection、quarantine。将 `knowledge/tool-control/scripts` 迁往 `tool-assets` 或具体 Adapter，先生成依赖图和兼容映射。

### DL-KNW-140 Open Design 双向转换

旧 Open Design 的 prompts/templates/skills/plugins/design systems/examples 分别转为 MethodCard、Domain Template、Capability Definition、Token、BenchmarkCase、ToolActionPlan。反向导出仅生成可选 Open Design Host Export Package。

### DL-KNW-150 权利与大师研究

分批治理 162 条来源；无法确认的永久 quarantine。大师研究只提炼方法、语境和可解释视觉原则，不做姓名仿制器。

P1 Gate：全部知识分类；大文件不入 Git；无 candidate/quarantine 运行时调用；OS 迁移仍 DEFERRED。

## 五、P2：设计智能与职业领域黄金纵切

### DL-CORE-100 现有内核核验

核验 13 阶段状态机、21 对象、Memory、Quality、Delivery、Federation E2E 的真实代码、fixture、正负测试和证据等级；不重复造轮子。

### DL-INT-100 Design IR 与 ToolActionPlan

固定链路：

```text
Brief → Context → Reference DNA → Directions → 人工锁定
→ Design IR → ToolActionPlan → Permission → Dry-run
→ Execute → Readback → Quality Review → Preflight
→ Editable Handoff → Evidence
```

Design IR 必须中立表达 canvas/artboard/timebase、text/image/vector/3D/audio/video nodes、style/token/constraint、版本/diff/rollback、rights/asset ref；禁止工具私有字段污染。

### DL-DOM-100 第一批黄金领域

按顺序完成 UI/UX、E-commerce、Brand。每个领域必须有：十要素 Domain Pack、真实 Brief、正例、失败例、Rubric、Preflight、可编辑 Handoff 和人工评分表。

### DL-DOM-110 第二批职业领域路线图

第一批通过后再按以下顺序展开：

1. Graphic / Editorial / Packaging；
2. 3D / Spatial / Exhibition；
3. Motion / Video / Audio；
4. Game Visual（仅以 MiniGame Fixture 验证）。

每批只同时激活一个领域，完成同一十要素和黄金案例后再扩展。

P2 Gate：一个真实 Brief 能生成可解释 Design IR 与 ToolActionPlan；UI/UX、电商、品牌至少完成契约级黄金案例。

## 六、P3：工具执行与读回

### DL-ADP-100 Registry 与合同

统一 Adapter Registry：canonical、alias、transport、capability、support、evidence、exact SHA。状态拆分 installed/connected/enumerated/executed/readback/production-ready，修复 Eagle schema，更新 PS/AI/FFmpeg/Open Design/ComfyUI/H3 真实等级。

所有写操作统一：

```text
capability negotiation → plan validation → permission → dry-run
→ execute → state readback → artifact readback → rollback → evidence
```

### DL-ADB-PS-100 Photoshop E3

在专用 fixture 中冷启动，创建分层 1920×1080 PSD，含文本、智能对象、调整层、蒙版、分组；保存、关闭重开、读取图层与字体、导出 PNG、回滚、重复三次。成功后才从 E1 升 E3。

### DL-ADB-AI-100 Illustrator E3

保持 MCP CC2024+ 版本门诚实；用受控 JSX fixture 建 AI 文件、画板、文本、矢量、色板、图层，重开读回并导出 PDF/SVG。99 个脚本必须抽样实测，不能凭入库宣称可用。

### DL-ADP-OPEN-100 Optional Host

Open Design 安装器只管理带 managed marker/upstream 的对象；不写私有数据库、不覆盖用户配置/Workspace/凭据；所有输入输出映射公共对象。

### DL-ADP-EAG-100 Eagle

等待用户在 GUI 启用 Web API。之后用测试库做查询、受控导入、readback 与回滚。此前仅 E1，不得写“已集成”。

### DL-ADP-MEDIA-100

ComfyUI/H3 保持历史 E3，不扩张、不重下载；新树如需升级必须重新绑定 SHA。FFmpeg 补 artifact/readback；记录输入/输出 hash、时延、内存和失败原因。

Figma、Penpot、Blender、Inkscape、OpenPencil、视觉模型 Provider 均保持 E0/VALIDATION，直到 PS 或 AI 有一个 E3。Flue 继续隔离。

P3 Gate：至少一个专业工具 E3，且可重复、可重开、可读回、可回滚。

## 七、P4：质量、生产与轻量入口

### DL-QLT-100

建立确定性规则 → 视觉模型信号 → 专业 Rubric → 专家复核 → 用户决策的质量管线。模型评分只能辅助，不能替代 Jury。

### DL-QLT-110

覆盖构图、层级、排版、字体、色彩、比例、材质、光影、动效、空间、可读性、可访问性、原创性、商业可信度与反 AI 廉价感。每条规则必须有反例、边界、严重度、检查方式与修复建议。

### DL-PRD-100

实现 Print、Digital/UI、E-commerce、Video/Motion、3D/Spatial、Game 的 Preflight Profile；完成 UI/UX、电商、品牌各一份无客户隐私的真实交付包。

### DL-QLT-120 人工 Jury

五域评分 ≥82、偏好 ≥70%、12 证据卡人工校准、FalsePassRate <2%。AI 不得代填。

### DL-UI-100 轻量前端

只在黄金纵切稳定后实现：项目总览、Brief、11 步进度、Directions、只读 Design IR、Quality、Preflight、Handoff、Adapter 状态、Knowledge Staging、Evidence。前端不是事实源、不是画布、不是 Agent Runtime。

P4 Gate：至少一份可编辑商业级交付通过 Preflight；Jury 完成或明确 BLOCKED。

## 八、P5：证据与发布

### DL-EVD-100

从同一证据记录生成 Project Status、Adapter Reconciliation、Knowledge Inventory、Domain Readiness、Release Readiness。exact SHA 为空即失败；测试定义数量不得冒充执行结果。

### DL-REL-100

人工门：Jury、独立复审/Attestation、来源补全、分支保护、Eagle GUI、真实 Adobe fixture 写入、OpenPencil 试点。OS 迁移始终 DEFERRED。

### DL-REL-110

通过本地完整验证、PR exact-head CI、独立复审、main CI、GitHub readback、三端 SHA 一致、干净工作树后，才生成 release package。

## 九、P6：未来 OS 迁移

状态固定 `DEFERRED`。只有 OS 的 Candidate→Review→Verified、稳定 API/Schema、无损 provenance/license/version/SHA、批量导入+回读+回滚+幂等、稳定 Query API、Domain Pack 回归和用户批准全部满足后才执行。

迁移后 OS 是知识权威；DESIGN-LAB 停止维护权威知识副本，仅保留可追溯 projection、编译产物、Domain Pack、评分器、工具契约和必要缓存。

## 十、执行顺序

```text
P0 事实/身份/报告/反漂移
→ P1 临时知识治理与多格式转换
→ P2 Design IR + UIUX/电商/品牌
→ P3 Photoshop 或 Illustrator E3
→ P4 质量、生产、轻量入口
→ P5 证据与发布
→ P6 等待 OS 就绪
```

最终判断标准：不以文档、脚本或 Adapter 数量衡量，而以“专业设计判断可调用、真实软件可受控执行、结果可读回、可交付可编辑文件、证据绑定 exact SHA”衡量。
