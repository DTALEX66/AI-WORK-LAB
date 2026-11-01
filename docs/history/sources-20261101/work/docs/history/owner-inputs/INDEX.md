# WORK-LAB 资料总入口

查文件先从本页进入；按原文件名、日期、任务编号或包内成员检索，不再依赖 Record 外部路径。
这是资料导航和历史来源登记，不是新的任务权威。当前执行仍读取 WORK-LAB-AUTHORITY.md 与唯一 CURRENT。

## 当前任务与历史摘要

- [当前权威收敛任务包](../../../taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md)
- [当前路线图](../../current/authority-convergence-20261019/ROADMAP.md)
- [权威收敛报告](../../current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md)
- [UI 历史交接（FROZEN_20261019，2026-10-19 汇总归档）](../archive/HANDOFFS-AND-PROMPTS-20261019-MANIFEST.json)：成员 NEXT-AGENT-PROMPT.md
- [历史关键信息与沿用边界](HISTORICAL-KEY-POINTS.md)
- [本次归档、去重、压缩及验证记录](RECORD-ARCHIVE-REPORT.md)
- [可搜索文件目录](CATALOG.html)：可按文件名、包内路径、材料分类、原位置筛选。
- [完整文件登记 JSON](RECORD-ARCHIVE-REGISTER.json) / [CSV](RECORD-ARCHIVE-REGISTER.csv)
- [完整包内成员登记 JSONL](RECORD-ARCHIVE-MEMBERS.jsonl) / [CSV](RECORD-ARCHIVE-MEMBERS.csv)
- [全部 Record 文件归属盘点](RECORD-SOURCE-CENSUS.json)：包括明确排除的其他项目材料。
- [去重登记](RECORD-DEDUPLICATION.json) / [合并压缩登记](RECORD-CONSOLIDATION.json) / [混合包范围](RECORD-MIXED-ARCHIVE-SCOPE.json)

## 如何定位与提取

在项目根用已有 Python 执行 `scripts/maintenance/owner_material_catalog.py find "关键词"`。
`find` 同时查原文件名、分类、别名和包内成员，返回资料 ID、仓内路径与完整嵌套成员链。`--limit 0` 显示全部命中。
`extract WL-REC-0001` 将指定资料提取到 `.project-local/artifacts/material-lookup/`，校验摘要，不执行材料中的命令。
`verify` 校验仓内全部文件和压缩包成员；显式加 `--source-root "D:/All projects/Record"` 才核对源目录。
当前机器 Python 入口为 `.project-local/toolchains/wl-py311/Scripts/python.exe`；其他机器动态发现现有解释器。

登记规则：相同 SHA-256/大小归为同一内容身份；所有源文件名、来源及成员路径保留为别名。
同名不同内容保留不同版本；历史报告的 PASS、SHA、安装状态只代表原报告时间，不能用作当前事实。
历史资料合并为无损 ZIP；现行输入不改字节。不可变 ZIP 内部的重复成员只在目录中分组，不改写原包。

后续增量材料先核对已有摘要，再追加源别名/版本和包内成员登记，运行 `build-index` 与 `verify`。
不要另建第二个资料目录或任务账本；没有找到文件时报告具体 ID/路径/摘要缺口，不用新摘要冒充原件。

## 原文件及别名目录


本次登记 **107 条资料**及 **2465 条包内成员**。下表链接指向规范存储；压缩资料的成员链在 JSON/CSV 和可搜索目录中完整列出。


## 项目派生归档容器

以下为既有资料整理或用户授权的项目内交接归档；不冒充 Record 源文件，不改变 Record 来源盘点。成员可通过 find 查询。

- WL-STORE-20261009：[WORK-LAB-HISTORICAL-RECORDS-20261009.zip](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>)；HISTORICAL_DERIVED_STORAGE_NOT_TASKPACK。
- WL-STORE-AGENTRULES-20261024：[WORK-LAB-AgentRules-Governance-Intake-20261024.zip](<20261024/WORK-LAB-AgentRules-Governance-Intake-20261024.zip>)；HISTORICAL_DERIVED_HANDOFF_NOT_TASKPACK。

### TASK_HANDOFF

| ID | 原位置 / 包内位置 | 身份 | 规范存储 |
| --- | --- | --- | --- |
| WL-REC-0001 | 00_总控启动提示词.md | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/00_总控启动提示词.md>) |
| WL-REC-0009 | 07_WORK-LAB_工作区接入交接.md | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0022 | START-ANY-AGENT.md | 项目历史 | [原件](<../../../taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/taskpacks/current/WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916/START-ANY-AGENT.md>) |
| WL-REC-0023 | TASKPACK (2).md | 项目历史 | [原件](<../../../taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/taskpacks/current/WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916/TASKPACK.md>) |
| WL-REC-0024 | TaskPack(1).md | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/TaskPack(1).md>) |
| WL-REC-0025 | TASKS.json | 项目历史 | [原件](<../../../taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/taskpacks/current/WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916/TASKS.json>) |
| WL-REC-0029 | WORK-LAB-AUTHORITY-RESET-FINAL-TASKPACK-20260918-v2.zip | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0031 | WORK-LAB-FULL-PROJECT-SCOPE-20260916.md | 项目历史 | [原件](<../../../taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree/taskpacks/current/WORK-LAB-UNIVERSAL-WORKFLOW-TASKPACK-20260916/WORK-LAB-FULL-PROJECT-SCOPE-20260916.md>) |
| WL-REC-0032 | WORK-LAB-HERMES-MASTER-TASKPACK-2026-09-07.md | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0033 | WORK-LAB-INTEGRATED-TASKPACK-20260916.zip | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0034 | WORK-LAB-NATIVE-FIRST-TASKPACK-2026-09-12.zip | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0035 | WORK-LAB_MASTER_ATLAS_2026-09-29.zip | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0041 | WORK-LAB_本对话最终任务包_20261009.zip | 当前输入 | [原件](<20261009/WORK-LAB_本对话最终任务包_20261009.zip>) |
| WL-REC-0042 | WORKLAB_CODEX_PROMPT.md | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/WORKLAB_CODEX_PROMPT.md>) |
| WL-REC-0045 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/work-lab-vertical.html | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0046 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/index.html | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0047 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/interaction-check.json | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0048 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/work-lab-square.html | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0051 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/work-lab.html | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0052 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/case-content.json | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0053 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/work-lab-banner.html | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0054 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/preview.html | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0055 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/work-lab-copy.md | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0056 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/README.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0057 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/qa-report.json | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0058 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/work-lab-design-tokens.json | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0066 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/fonts/Noto-OFL.txt | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0067 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/fonts/Inter-OFL.txt | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0100 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/asset-manifest.json | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0105 | WORK-LAB_9DE58194E69BB8E88488E88395E58C95E4BB8AE585.zip | 当前输入 | [原件](<20261019/WORK-LAB_权威收敛任务包_20261019.zip>) |

### AUDIT

| ID | 原位置 / 包内位置 | 身份 | 规范存储 |
| --- | --- | --- | --- |
| WL-REC-0002 | 01_审计报告与三项目融入建议.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0003 | 01_审计结论.md | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/01_审计结论.md>) |
| WL-REC-0006 | 02_WORK-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/02_WORK-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt>) |
| WL-REC-0008 | 05_附件完整性与工作簿审计.json | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0030 | WORK-LAB-FULL-AUDIT-AND-REPAIR-2026-09-15.zip | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0039 | WORK-LAB_审计收敛报告_2026-10-01.html | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/WORK-LAB_审计收敛报告_2026-10-01.html>) |
| WL-REC-0040 | WORK-LAB_审计裁决_2026-10-01.json | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/WORK-LAB_审计裁决_2026-10-01.json>) |
| WL-REC-0104 | AAOS-WORK-DESIGN-cloud-audit-20261011.zip | 当前输入 | [原件](<record-20261011/originals/AAOS-WORK-DESIGN-cloud-audit-20261011.zip>) |
| WL-REC-0106 | WORK-LAB_独立闭环审计包_20261021.zip | 当前输入 | [原件](<20261021/WORK-LAB_独立闭环审计包_20261021.zip>) |
| WL-REC-0107 | WORK-LAB_既有规划对账与独立闭环交接包_20261023.zip | 当前输入 | [原件](<20261023/WORK-LAB_既有规划对账与独立闭环交接包_20261023.zip>) |

### BLUEPRINT_RESEARCH

| ID | 原位置 / 包内位置 | 身份 | 规范存储 |
| --- | --- | --- | --- |
| WL-REC-0004 | 01_汇总报告.html | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0005 | 02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx>) |
| WL-REC-0007 | 03_价格与额度工作簿.xlsx | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0043 | 三项目_AI生态全生命周期收敛实施清单_2026-10-01.json | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0044 | 三项目_AI生态全生命周期收敛最终方案_2026-10-01.html | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0101 | 总览.html | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0102 | 汇总报告.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |

### UI_REFERENCE

| ID | 原位置 / 包内位置 | 身份 | 规范存储 |
| --- | --- | --- | --- |
| WL-REC-0010 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/app.js | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0011 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/index.html | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0016 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/README.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0017 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/reports/ASSET_PROMPTS.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0018 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/reports/CASE_COPY.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0019 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/reports/QA.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0020 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/reports/REFERENCE_AUDIT.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0021 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/styles.css | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0027 | UI_COMPONENT_ADOPTION_PLAN.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0028 | UI_KIT_AUDIT.md | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0036 | WORK-LAB_UI_FRONTEND_TASKPACK_20260930.zip | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0037 | WORK-LAB_UI前端更新任务包_20261009.zip | 当前输入 | [原件](<20261009/WORK-LAB_UI前端更新任务包_20261009.zip>) |
| WL-REC-0038 | WORK-LAB_UI开发资料总包_按批次.zip | 项目历史 | [原件](<../archive/recovered-originals/RECORD-20261008/WORK-LAB_UI开发资料总包_按批次.zip>) |
| WL-REC-0049 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/ui-assets.json | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0050 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/brand-ui-kit.html | 共享历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0079 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/source_ui/work-lab/index.html | 项目历史 | [压缩包成员](<record-20261009/WORK-LAB-HISTORICAL-RECORDS-20261009.zip>) |
| WL-REC-0103 | WORK-LAB_UI前端深化任务包_v2.zip | 当前输入 | [原件](<record-20261010/originals/WORK-LAB_UI前端深化任务包_v2.zip>) |

### UI_ASSET

| ID | 原位置 / 包内位置 | 身份 | 规范存储 |
| --- | --- | --- | --- |
| WL-REC-0012 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/assets/cases/worklab-audit.webp | 项目历史 | [原件](<record-20261009/originals/DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/assets/cases/worklab-audit.webp>) |
| WL-REC-0013 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/assets/cases/worklab-hero.webp | 项目历史 | [原件](<record-20261009/originals/DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/assets/cases/worklab-hero.webp>) |
| WL-REC-0014 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/assets/cases/worklab-workflow.webp | 项目历史 | [原件](<record-20261009/originals/DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/assets/cases/worklab-workflow.webp>) |
| WL-REC-0015 | DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/favicon.svg | 共享历史 | [原件](<record-20261009/originals/DT_ALEX_STUDIOS_10_CASE_PORTFOLIO_COMPLETE_20261007 (1)/public/favicon.svg>) |
| WL-REC-0026 | Three_Project_Logos_BW_4K_0000_图层 2.jpg | 项目历史 | [原件](<record-20261009/originals/Three_Project_Logos_BW_4K_0000_图层 2.jpg>) |
| WL-REC-0059 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/brand-lockups.png | 共享历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/brand-lockups.png>) |
| WL-REC-0060 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab-keyvisual.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab-keyvisual.png>) |
| WL-REC-0061 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/deliverables/三项目品牌_UI基础套件.png | 共享历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/deliverables/三项目品牌_UI基础套件.png>) |
| WL-REC-0062 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/deliverables/三项目案例预览.png | 共享历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/deliverables/三项目案例预览.png>) |
| WL-REC-0063 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/deliverables/WORK-LAB_完整产品案例.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/deliverables/WORK-LAB_完整产品案例.png>) |
| WL-REC-0064 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/deliverables/三项目案例总览.png | 共享历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/deliverables/三项目案例总览.png>) |
| WL-REC-0065 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/fonts/Inter.ttf | 共享历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/fonts/Inter.ttf>) |
| WL-REC-0068 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/fonts/NotoSansCJKsc-Regular.otf | 共享历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/fonts/NotoSansCJKsc-Regular.otf>) |
| WL-REC-0069 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/08.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/08.png>) |
| WL-REC-0070 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/01.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/01.png>) |
| WL-REC-0071 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/04.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/04.png>) |
| WL-REC-0072 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/07.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/07.png>) |
| WL-REC-0073 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/05.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/05.png>) |
| WL-REC-0074 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/02.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/02.png>) |
| WL-REC-0075 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/10.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/10.png>) |
| WL-REC-0076 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/03.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/03.png>) |
| WL-REC-0077 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/06.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/06.png>) |
| WL-REC-0078 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/assets/work-lab/ui/09.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/assets/work-lab/ui/09.png>) |
| WL-REC-0080 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/04-palette.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/04-palette.png>) |
| WL-REC-0081 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/online-vertical.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/online-vertical.png>) |
| WL-REC-0082 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/09-journey.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/09-journey.png>) |
| WL-REC-0083 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/online-product-card.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/online-product-card.png>) |
| WL-REC-0084 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/01-hero.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/01-hero.png>) |
| WL-REC-0085 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/online-banner.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/online-banner.png>) |
| WL-REC-0086 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/07-flagship.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/07-flagship.png>) |
| WL-REC-0087 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/11-screens.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/11-screens.png>) |
| WL-REC-0088 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/qa-mobile.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/qa-mobile.png>) |
| WL-REC-0089 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/05-typography.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/05-typography.png>) |
| WL-REC-0090 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/08-architecture.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/08-architecture.png>) |
| WL-REC-0091 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/03-identity.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/03-identity.png>) |
| WL-REC-0092 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/online-square.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/online-square.png>) |
| WL-REC-0093 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/15-closing.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/15-closing.png>) |
| WL-REC-0094 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/02-overview.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/02-overview.png>) |
| WL-REC-0095 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/14-relation.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/14-relation.png>) |
| WL-REC-0096 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/13-digital.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/13-digital.png>) |
| WL-REC-0097 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/06-graphic.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/06-graphic.png>) |
| WL-REC-0098 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/10-interaction.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/10-interaction.png>) |
| WL-REC-0099 | 三项目_VI_UI_UX_作品集完整交付包.zip ! 三项目_产品案例/exports/work-lab/12-mockups.png | 项目历史 | [原件](<record-20261009/originals/mixed-vi-ui-ux/三项目_产品案例/exports/work-lab/12-mockups.png>) |
