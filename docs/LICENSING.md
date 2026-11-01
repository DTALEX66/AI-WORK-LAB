# 许可与权利范围（本仓的诚实口径）

`LICENSE` 里的 MIT **只覆盖本仓自己写的代码**：`backend/`、`packages/`、`domains/`（不含
`domains/design/design_lab/resources/` 里的随包原件）、`integrations/`、`apps/` 的壳与工具、
`scripts/`、`tests/`、`config/`。判据是文件头的 `SPDX-License-Identifier: MIT`，
数量由 `scripts/check_project_current.py` 现算，不在这份文档里抄一遍。

## 不在 MIT 授权范围内的东西

| 内容 | 位置 | 权利口径 |
|---|---|---|
| 随包发布的第三方与来源仓原件 | `domains/design/design_lab/resources/`、`vendor/` | 原样保留（inert blobs），不因本仓的 LICENSE 而改变其许可 |
| 按摘要逐字节迁入的历史原件 | `docs/history/sources-20261101/`、`docs/history/archive-objects-20261101/` | 保持来源仓原件字节；其许可与权利信息随行保留 |
| 带许可旁注的素材 | `*.license`（REUSE 风格 sidecar） | **逐个文件判定**，以旁注为准 |

## 必须由 owner 处置的一条事实

许可旁注里有 **5 个** 声明 `"redistributable": false`：

- `apps/workbench/brand/design-lab-mark.png.license`
- `apps/workbench/brand/design-lockup.svg.license`
- `apps/workbench/brand/design-mark.svg.license`
  （`LicenseRef-DESIGN-LAB-Brand`，作者 DTALEX66，品牌件，标注为不可再分发）
- 两个 `UNLICENSED-INTERNAL` 的内部归档件（一个 `.docx` 任务包、一个 CI E2 工件 `.zip`）

**这 5 个对象已经在本仓库里，而远程仓的可见性是 PUBLIC。** "标注不可再分发"与"已发布到公开远程"
是两件事，我不会用写一个 LICENSE 文件的方式把它抹平。可选处置（都需要 owner 拍）：

1. 由权利持有人（同一人 DTALEX66）改判这些件的可再分发性并更新旁注；
2. 或把它们从仓库移出，只保留摘要与位置登记（与本轮截图照片同一手法，字节不消失）。

## 与专业权利门的关系

字体、第三方素材、模型与商标的权利判定，在本项目里由 Rights gate 负责，
并按既有决定**不作为本仓的完成条件**；这份文件记录的是"现在声明了什么、没声明什么"，
不是"已经清 rights"。
