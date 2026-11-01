# Research Candidates Registry（第三方候选登记区）

- 更新：2026-09-04（DL-DIR-MIG-R1 规范化终版）
- 语义：`research/candidates/` 为 **CONDITIONAL_POC 索引区** —— 只登记第三方候选的裁决状态与来源；**完整源码不进入 Git**，保存在 ignored vendor cache（`.project-local/cache/vendor/`），可在需要时按 `cache` 列取用。
- 治理依据：`DESIGN-LAB-DIRECTORY-MIGRATION-CLEANUP-TASKPACK-2026-09-01-3.md` 第 5 节（CONDITIONAL_POC = 尚未资格化，`research/candidates/<id>.md` 登记 + 源码在 ignored vendor cache）。许可逐项核实记录在 `design-lab/research/global-absorption/QUARANTINE_REGISTRY.json`（162 源）。
- 每仓原始完整内容（含 LICENSE/SOURCE.md/README）：`.project-local/cache/vendor/<id>`（gitignored，本机可随时取用；不回 Git）。

## 一、整体候选仓清单（2026-08-13/14 收录 → 2026-09-04 移出 Git）

| 候选 | 文件数 | 来源（URL） | 许可 | 裁决 | cache 键 |
|---|---:|---|---|---|---|
| baoyu-design | 219 | github.com/JimLiu/baoyu-design | MIT | CONDITIONAL_POC | baoyu-design |
| ecommerce-ai | 223 | github.com/kangise/ecommerce-ai-skills | CC0-1.0 | CONDITIONAL_POC | ecommerce-ai |
| genjutsu | 101 | github.com/AThevon/genjutsu | MIT | CONDITIONAL_POC | genjutsu |
| motion-forensics | 122 | github.com/voidmatcha/ui-clone-skills | Apache-2.0 | CONDITIONAL_POC | motion-forensics |
| ui-ux-pro-max | 41 | github.com/nextlevelbuilder/ui-ux-pro-max-skill | MIT | CONDITIONAL_POC | ui-ux-pro-max |
| ultimate-uiux | 54 | github.com/ca-who-codes/ultimate.UIUX.design.skills | MIT | CONDITIONAL_POC | ultimate-uiux |
| tool-control | 120 | 归档库（creold/photoshop-scripts、creold/illustrator-scripts、Comfy-Org、style-dictionary 等，README 逐项列源） | MIT / Apache-2.0（逐子树） | CONDITIONAL_POC | tool-control |

> **回源覆盖边界（2026-10-06 对账）**：本节 7 行 + 下节 30 行 = **37 行**，但
> `research/candidates/observations/github-observation-20261006T105000Z.json` 自报
> `counts.recordedInReadme = 36`。差额就是 `tool-control`：它的"来源"是若干归档库的合集，
> **没有单一 canonical upstream**，所以未被该轮回源解析；它在 `CANDIDATE-TAXONOMY.json` 中
> `canonicalUrl` 为 `null`（`scripts/build_candidate_taxonomy.py` 已明确声明这一处理，非遗漏）。
> 口径约束：**"979 个上游已观测"不包含 `tool-control`**；其许可为逐子树声明，尚未逐项读原文核实。

### visual-quality 子仓（30 个第三方收录，2026-08-14 收录）

> 计数对账 2026-10-06：下表 **30 行**，与主检出（`D:/All projects/DESIGN-LAB`）本机 ignored
> vendor cache `.project-local/cache/vendor/visual-quality__*` 的 **30 个目录逐名一致**；
> 同检出下 vendor cache 总计 37 个目录 = 本节 30 + 上一节 7。
> 原小标题写「25 个」，与以上两项实测均不符，已按实测更正为 30。
> 注：本分支的 `CANDIDATE-TAXONOMY.json` 仍是 7 条种子版，尚未包含 visual-quality 条目；
> 投影到 37 条的版本在 `qoder/designlab-global-capability-intake-20261006`（`73426936`）。

| 候选 | 文件数 | 来源 | 许可 | cache 键 |
|---|---:|---|---|---|
| affiliate-skills | 171 | github.com/Affitor/affiliate-skills | MIT | visual-quality__affiliate-skills |
| ppt-agent | 121 | github.com/Akxan/ppt-agent-skill | MIT | visual-quality__ppt-agent |
| hallmark | 109 | github.com/Nutlope/hallmark | MIT | visual-quality__hallmark |
| document-design-system | 98 | github.com/Avinava/document-design-system | MIT | visual-quality__document-design-system |
| qiaomu-design | 83 | github.com/joeseesun/qiaomu-design | MIT | visual-quality__qiaomu-design |
| springy-motion | 58 | github.com/OtherdaysStudio/springy-motion | MIT | visual-quality__springy-motion |
| extract-design-system | 55 | github.com/arvindrk/extract-design-system | MIT | visual-quality__extract-design-system |
| game-ui-mobile | 55 | github.com/dungnotnull/game-ui-mobile-friendly-design-agent-skill | MIT | visual-quality__game-ui-mobile |
| brand-identity-generator | 41 | github.com/AbdulkareemKR/brand-identity-generator | MIT | visual-quality__brand-identity-generator |
| motion-design-skill | 21 | github.com/LottieFiles/motion-design-skill | MIT | visual-quality__motion-design-skill |
| design-motion-principles | 19 | github.com/kylezantos/design-motion-principles | MIT | visual-quality__design-motion-principles |
| hue | 18 | github.com/dominikmartn/hue | MIT | visual-quality__hue |
| logo-designer | 16 | github.com/neonwatty/logo-designer-skill | MIT | visual-quality__logo-designer |
| screenshot-to-ds | 15 | github.com/WCF900905/screenshot-to-design-system | MIT | visual-quality__screenshot-to-ds |
| brand-systems | 14 | github.com/arome3/evidence-based-brand-systems | MIT | visual-quality__brand-systems |
| claude-dolphin | 14 | github.com/nyldn/claude-dolphin | MIT | visual-quality__claude-dolphin |
| design-thinking | 14 | github.com/kopfwelt/skills | MIT | visual-quality__design-thinking |
| swiftui-design | 14 | github.com/Wholiver/swiftui-design-skill | MIT | visual-quality__swiftui-design |
| claude2figma | 13 | github.com/senlindesign/claude2figma | MIT | visual-quality__claude2figma |
| blender-3d | 11 | github.com/jithinolickal/blender | Apache-2.0 | visual-quality__blender-3d |
| brandbook-skill | 11 | github.com/echowang97/brandbook-skill | MIT | visual-quality__brandbook-skill |
| brand-identity | 10 | github.com/SkillMedev/brand-visual-identity | MIT | visual-quality__brand-identity |
| taste-skill | 8 | github.com/Leonxlnx/taste-skill | MIT | visual-quality__taste-skill |
| ai-graphic-design | 7 | github.com/designrique/ai-graphic-design-skill | MIT | visual-quality__ai-graphic-design |
| dataviz-critique | 7 | github.com/zhanyi789/dataviz-critique-skills | MIT | visual-quality__dataviz-critique |
| game-creative | 7 | github.com/wotonger/GameCreative-skills | MIT | visual-quality__game-creative |
| ux-audit-skill | 7 | github.com/EliaAlberti/ux-audit-skill | MIT | visual-quality__ux-audit-skill |
| interface-design | 6 | github.com/Dammyjay93/interface-design | MIT | visual-quality__interface-design |
| visual-note-card | 6 | github.com/beilunyang/visual-note-card-skills | MIT | visual-quality__visual-note-card |
| design-md-skill | 5 | github.com/arumwu/design-md-skill | MIT | visual-quality__design-md-skill |

## 二、DESIGN 自有知识（2026-09-04 移出 candidates）

原 `research/candidates/visual-quality/` 根下的 18 个**方法论文档**（AI_SLOP_FAILURE_MODES、COLOR_MATERIAL_LIGHT、COMPOSITION_AND_RHYTHM、DEPTH_TEXTURE_REALISM、DESIGN_FEELING_MODEL、DESIGN_TASTE_AXES、MASTER_GRADE_FINISHING_PROTOCOL、MASTER_METHOD_USE_POLICY、MASTER_RESEARCH_PROTOCOL、PHOTOGRAPHY_AND_IMAGE_DIRECTION、PHOTOREALISM_AND_AI_ARTIFACT_QA、STYLE_ANALYSIS_PROTOCOL、STYLE_SYNTHESIS_RULES、TYPOGRAPHY_CRAFT、VISUAL_JURY_PROTOCOL、VISUAL_QUALITY_MODEL、VISUAL_REFERENCE_DNA_PROTOCOL、VISUAL_REFINEMENT_LOOP）经核实为 **DESIGN 自有视觉质量协议族**（非第三方），已移入自有知识区：

```
design-lab/research/visual-quality/
```

## 三、后续（DL-DIR-030 资格化）

- 每候选需完成真实用例验证（官方 URL 精确 SHA 拉取 → 校验 → sandbox 测试 → DESIGN 真实场景写后读回）后裁决：
  - 通过 → ABSORB_MINIMAL 进 `packages/capabilities/<id>`（保留许可+来源+测试）
  - 方法参考 → LOCK_REFERENCE（`vendor/sources.lock.json` 登记）
  - 不合格 → REJECT_REMOVE（decision ledger 记录）
- 未裁决前源码只存在 `.project-local/cache/vendor/`（本机）；fresh clone 不含第三方源码（符合第三方隔离目标）。
