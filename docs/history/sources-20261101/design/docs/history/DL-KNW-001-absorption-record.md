# DL-KNW-001 — 设计类资料吸收记录

- 任务：DL-KNW-001 Knowledge Acquisition（人工资料审核与吸收）
- 状态：✅ 十三批吸收完成（2026-08-14）——35 个设计技能源码级 vendoring + 7 reference 登记
- 方式：GitHub 公开设计 SKILL/项目，MIT/Apache/CC0 许可核验后源码级 vendoring；无 LICENSE 文件者降级 reference-only

## 吸收清单（源码级 vendoring，含 LICENSE + SOURCE.md）

### 批次 1（PR #17，2026-08-13）

| 来源 | 许可 | 落点 | 内容 |
|---|---|---|---|
| Hallmark | MIT | `knowledge/visual-quality/hallmark/` | anti-AI-slop、21 宏结构、60+ 组件配方、slop-test |
| Taste-Skill | MIT | `knowledge/visual-quality/taste-skill/` | brief 推断、设计阅读、防默认纪律 |
| Huashu-Design | MIT | `knowledge/production/huashu-design/` | HTML 原型、幻灯片、动画、评审、品牌协议 |
| UI/UX Pro Max | MIT | `intelligence/ui-ux-pro-max/` | 84 风格、192 色板、74 字体配对、98 UX 指南 |

### 批次 2–3（PR #18–#19）

| 来源 | 许可 | 落点 | 内容 |
|---|---|---|---|
| motion-design-skill (LottieFiles) | MIT | `visual-quality/motion-design-skill/` | 动效设计原则 |
| design-motion-principles | MIT | `visual-quality/design-motion-principles/` | 动效设计 skill |
| shipit-ui | MIT | `intelligence/shipit-ui/` | 11 UI 设计 skills |
| Front-End-Design-Checklist | CC0 | `knowledge/standards/front-end-design-checklist/` | 前端设计检查清单 |

### 批次 4（PR #30）— 游戏/3D/品牌

game-ui-mobile（MIT）、blender-3d（Apache）、motion-engine（MIT）、brand-systems（MIT）、brand-identity（MIT）、ai-graphic-design（MIT）

### 批次 5（PR #31）— 设计系统/Figma/演示

design-system-prompt（1889⭐ MIT）、claude2figma（MIT）、extract-design-system（MIT）、anydesign（MIT）、ppt-agent（MIT）、swiftui-design（MIT）

### 批次 6（PR #32）— 无障碍/品牌书/logo

claude-dolphin（MIT）、ux-audit-skill（MIT）、claude-design-skill（MIT）、brandbook-skill（MIT）、logo-designer（MIT）、ecommerce-ai（CC0）、screenshot-to-ds（MIT）

### 批次 7（PR #33）— 动效取证/设计思维

motion-forensics（Apache）、springy-motion（MIT）、design-thinking（MIT）、web-content-designer（Apache）

### 批次 8（PR #34）— creative coding/游戏管线

genjutsu（216⭐ MIT）、game-creative（MIT）、ai-product-os（MIT）

### 批次 9（PR #35）— 本地设计系统

baoyu-design（3411⭐ MIT）、design-md-skill（MIT，74 品牌参考）

### 批次 10（PR #36）— 文档/图表/品牌/上下文

document-design-system（MIT）、dataviz-critique（MIT）、brand-identity-generator（MIT）、ultimate-uiux（MIT）+ ux-writing-skill（147⭐ **无 LICENSE → reference-only 登记**）

### 批次 11–13（PR #58–#60，2026-08-14）— 色彩/设计系统/营销

- hue（797⭐ MIT）：色彩系统 skill + 12 模板 → `knowledge/visual-quality/hue/`
- qiaomu-design（489⭐ MIT）：乔木设计系统 + 50+ 真实品牌 DESIGN.md（Linear/Stripe/Vercel/Apple/Notion）→ `knowledge/visual-quality/qiaomu-design/`
- interface-design（5438⭐ MIT）：界面设计系统模板 → `knowledge/visual-quality/interface-design/`
- visual-note-card（78⭐ MIT）：中文视觉笔记卡片/信息图 → `knowledge/visual-quality/visual-note-card/`
- affiliate-skills（606⭐ MIT）：32 联盟营销 skill → `knowledge/visual-quality/affiliate-skills/`

## 治理（每份均含）

- `LICENSE` 副本（随吸收保留版权声明）
- `SOURCE.md`：来源/作者/许可/日期/用途/再分发/模型输入/商用状态
- SOURCE_REGISTRY.json 登记（`vendor-adapt`/`adopt-now`，schema 校验通过）
- vendored 目录进 `verify_license_coverage.py` EXCLUDE（REUSE 语义：目录自带 LICENSE 覆盖源码+二进制）
- ux-writing-skill（无 LICENSE 文件）→ `reference`/`reference-now`，不 vendoring

## 未吸收（按边界规则）

- 各来源大文件（huashu assets 30MB、ppt-agent assets/ppt-output 7MB、ecommerce-ai i18n 11.6MB、design-md palette.png 542KB）
- 无 LICENSE 文件的项目（ux-writing-skill 等）→ reference-only
- NO-LICENSE 项目（plugin87/ux-ui-agent-skills 496⭐ 等）→ 不吸收

## 证据

- `VERIFY_SOURCE_REGISTRY=OK`（162 条，0 错误）
- `VERIFY_DESIGN_LAB=OK total=11 failed=0`
- `LICENSE_COVERAGE=OK`（source headers + binary sidecars）
- 全测试 137 passed + 5 subtests
- `CAPABILITY_INDEX=OK count=2222`

## 下一步（人工）

1. 吸收内容评审：确认各 skill 与 DESIGN-LAB 能力域映射（visual-quality / production / intelligence）
2. 提炼 MethodCard / BenchmarkCase（从吸收的方法到可测能力）
3. Design assets 素材到位后：E3 本地有界提取
