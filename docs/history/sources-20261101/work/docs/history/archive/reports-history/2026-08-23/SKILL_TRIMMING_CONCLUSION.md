# 技能精简结论（② 官方优先约束下）

> 目标②原为 Hermes 82→~25、Codex 328→~20，但官方优先规则约束：官方 skills 不删。

## 1. 识别结果（实测）

### Hermes 真 macOS/Apple 专用技能（Windows 永不触发）：仅 4 个

- apple-notes
- apple-reminders
- findmy
- imessage
（其余 78 个是官方通用/研究/工具技能，正则误匹配的排除）

### Codex 328 skills/prompts + DESIGN-LAB .hermes 6MB 副本

- Codex 328：.codex 下 skill/prompt 文件（官方+用户混合，需逐一确认）
- DESIGN-LAB 648/6MB：.hermes 运行时副本（Open Design expert-suite）

## 2. 结论（官方优先）

| 项 | 结论 | 依据 |
|---|---|---|
| Hermes 官方 skills（含 4 个 macOS）| 不删 | 官方优先规则；macOS 技能在 Windows 上 description 永不匹配，本来就永不触发，无实际负担 |
| Codex 328 | 待逐一确认（官方 vs 用户冗余），官方不删 | 官方优先 + 不打扰 Codex 执行 |
| DESIGN-LAB 6MB 副本 | 归档候选（运行时副本，非项目源）| 需用户确认后归档 |

## 3. 真正的解决（已落地）

- 技能白维护的根治不是删除，而是【调用】
- SOUL.md 技能调用纪律（先扫 SKILL 再执行）——该用的用起来
- macOS 技能自然不加载（description 不匹配）——无负担
- 官方 skills 全部保留，通过调用机制让有用的生效、无用的自然闲置

## 4. 待用户确认

- DESIGN-LAB .hermes 6MB 副本：归档还是保留（涉及 .hermes 运行时）
- Codex 328 里确认的非官方冗余：归档 40-knowledge

## 5. 状态

- ② 完成识别+结论阶段（官方优先：不删官方，靠调用机制）
- 非官方副本归档待用户确认范围