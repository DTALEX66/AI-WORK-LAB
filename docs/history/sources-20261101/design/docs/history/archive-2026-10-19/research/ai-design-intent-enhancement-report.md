# AI 设计意图理解增强方案 — 调研报告

## 一、审计发现：当前问题

### 1.1 我们缺的不是模型，是"意图翻译层"

当前工作流：用户说"开始" → AI 直接生成图

问题链条：
```
用户意图 "文化墙展厅设计"
    ↓ (无翻译层)
AI 理解 "现代大堂+蓝色墙+金色的字" ← 猜测
    ↓
输出 80% 像高端酒店大堂，20% 像文化墙
    ↓
用户说"不对" → 无反馈机制 → 再次猜测
```

### 1.2 缺什么

| 缺失环节 | 现状 | 应该有的 |
|---|---|---|
| 设计简报锁brief | 直接猜 | Discovery Form（30秒表单锁定需求） |
| 品牌规范提取 | 凭感觉 | Brand Spec Extraction（从URL/PDF/截图提取） |
| 视觉方向确认 | 无 | Direction Picker（5种预置方向供选择） |
| 结构化自检 | 无 | P0/P1/P2 Checklist（必须全部通过） |
| 反AI痕迹审计 | 无 | Anti-Slop Checklist（禁止紫渐变、emoji图标等） |
| 设计系统绑定 | 无 | DESIGN.md（品牌色/字体/间距/布局规则） |
| 技能模板 | 无 | SKILL.md（特定产物的结构DNA） |
| 记忆复用 | 无 | Memory Hooks（记住用户偏好和历史反馈） |

---

## 二、解决方案：Open Design 官方 Anti-Slop 引擎

### 2.1 六层防御体系（Open Design 已内置）

| 层级 | 名称 | 作用 | 来源 |
|---|---|---|---|
| 1 | Discovery Form | 生成前锁定需求（受众/品牌/规模/语气） | `discovery.ts` |
| 2 | Brand Extraction | 从URL/PDF/截图自动提取品牌规范 | Bash + Read + WebFetch |
| 3 | 5维自检 | Philosophy/Hierarchy/Execution/Specificity/Restrait | 每张图生成后自动运行 |
| 4 | P0/P1/P2 Checklist | 按优先级列出必须满足的设计规则 | `references/checklist.md` |
| 5 | Hard-coded Blacklist | 禁止紫渐变、emoji图标、左侧边框卡片等 | 硬编码在prompt中 |
| 6 | Honest Placeholders | 灰色占位符替代编造的"10x faster" | 强制规则 |

### 2.2 DESIGN.md — 设计系统的 Markdown 格式

核心洞察（来自 opendesigner.io 实验）：
- **Tokens（色值/字体/间距）只能解释 1/3 的差异**
- **剩下的 2/3 来自 prose 约束**：品牌色用在哪里、强调色何时出现、语气模式、反模式清单

9 段式结构：
```
1. Brand（品牌调性）
2. Color（OKLch 色彩空间，非 hex）
3. Typography（Display + Body + Mono 字体栈）
4. Spacing（基础单位 + 节奏注释）
5. Components（组件用法）
6. Layout（网格/断点/容器宽度）
7. Voice（语气规则）
8. Motion（动效规则）
9. Anti-patterns（禁止清单 ← 最关键）
```

官方提供 151+ 预置设计系统：Stripe / Linear / Vercel / Apple / Notion / Material...

---

## 三、具体落地方案

### 3.1 安装/吸收的技术栈

| 优先级 | 内容 | 形式 | 状态 |
|---|---|---|---|
| **P0** | DESIGN.md 设计系统 | Markdown 文件 | 官方 151+ 可直接用 |
| **P0** | Discovery Form | 交互表单 | 已内置 |
| **P0** | Anti-Slop Checklist | 强制规则 | 已内置 |
| **P0** | 5维自检 | 自动运行 | 已内置 |
| **P1** | Brand Extraction | 工具调用 | 需要URL/截图输入 |
| **P1** | Memory Hooks | 用户偏好记忆 | 需要配置 |
| **P1** | P0/P1/P2 Checklist | 自定义检查清单 | 需要按项目写 |
| **P2** | Direction Picker | 5种预置方向 | 已内置 |

### 3.2 针对本项目的具体行动

#### 步骤 1：为星云科技创建 DESIGN.md

```markdown
# Brand
B2B AI company. Trustworthy, professional, humanistic.

# Color
- Primary: oklch(0.55 0.25 250) /* Nebula Blue */
- Deep: oklch(0.35 0.15 250) /* Deep Space */
- Accent: oklch(0.75 0.15 85) /* Star Gold */
- Neutral: oklch(0.3 0.02 250) /* Galaxy Gray */
- Background: oklch(0.98 0.01 250) /* Star White */

# Typography
- Display: Source Han Sans Heavy / Montserrat Bold
- Body: Source Han Sans Regular / Montserrat Regular
- Data: Source Han Sans Medium / Montserrat Medium
- Scale: 12/14/16/20/24/32/48/64/80

# Spacing
- Base: 8px
- Scale: 4/8/12/16/24/32/48/64/96
- Vertical rhythm: prefer 64 or 96 between sections

# Anti-patterns
- No purple/violet gradients
- No generic emoji icons
- No rounded card with left colored border
- No hand-drawn SVG illustrations
- No Inter/Roboto as display face
- No invented metrics without source
- No filler "Feature One/Two" copy
- No warm beige/cream/peach backgrounds
```

#### 步骤 2：为文化墙设计创建 SKILL.md

```markdown
# Culture Wall Designer

## Pre-flight
- Read active DESIGN.md
- Read brand-spec.md (if exists)
- Confirm: wall dimensions, viewing distance, lighting conditions

## Checklist (P0 must all pass)
- [ ] Brand color accuracy (ΔE ≤ 3)
- [ ] Information hierarchy (far/mid/near 3 levels)
- [ ] Lighting uniformity ≥ 0.7
- [ ] Information density ≤ 40%
- [ ] Wheelchair accessible height 0.9-1.2m
- [ ] No flickering under 60Hz ambient light

## 5-Dim Self-Critique
1. Philosophy: does it feel like a culture wall, not a hotel lobby?
2. Hierarchy: does the eye land on company name first?
3. Execution: are letters properly kerned, not AI-garbled?
4. Specificity: every word specific to Nebula Tech?
5. Restraint: one accent used at most twice per zone?
```

#### 步骤 3：启用 Memory Hooks

在 Open Design 中配置记忆规则：
- "用户偏好 Linear/Vercel 融合风格"
- "不接受紫渐变、emoji 图标"
- "重视可见入口、无竖排"
- "CCTV 布局窗口保持不变"

---

## 四、对比：修复前 vs 修复后

| 维度 | 修复前 | 修复后 |
|---|---|---|
| 需求获取 | AI 猜测 | Discovery Form 30秒锁定 |
| 品牌规范 | 凭感觉 | DESIGN.md + Brand Extraction |
| 视觉方向 | 随机 | Direction Picker 5选1 |
| 质量检查 | 无 | P0/P1/P2 Checklist |
| AI痕迹 | 经常有紫渐变/emoji | Anti-Slop Blacklist |
| 反馈学习 | 无 | Memory Hooks 记住偏好 |
| 产物一致性 | 每张图风格不同 | 同一 DESIGN.md 保证一致 |

---

## 五、后续任务还差什么

### 已解决 ✅
- DLR-000~070, DLR-100 已完成
- 基础渲染能力（ComfyUI + SDXL）
- 展厅设计效果图

### 本方案新增能力 ✅
- Anti-Slop 引擎（6层防御）
- DESIGN.md 品牌系统
- 意图理解增强

### 仍缺的硬件依赖 ❌
| 任务 | 需要 | 可解性 |
|---|---|---|
| DLR-080 | Penpot 安装 + MCP 服务器 | 免费开源，可装 |
| DLR-090 | Blender + Krita/Inkscape | 免费开源，可装 |
| DLR-110 | Adobe PS/AI + Figma + Eagle | 需授权 |
| DLR-120 | OpenColorIO/OTIO/MaterialX | 免费开源，可装 |
| DLR-130 | Krita AI Diffusion / InvokeAI | 免费开源，可装 |
| DLR-140 | ArcheAxis 接收门 | 需外部配合 |
| DLR-150 | 依赖全部完成 | 依赖 |

---

## 六、推荐行动

1. **立即**：为星云科技创建 `packages/design-system/nebula-tech/DESIGN.md`
2. **立即**：安装 Penpot → 推进 DLR-080
3. **可选**：安装 Blender + Krita → 推进 DLR-090
4. **可选**：安装 OpenColorIO + MaterialX → 推进 DLR-120

---

*调研来源: Open Design 官方文档 / opendesigner.io / GitHub nexu-io/open-design / IxDF / IBM Prompt Engineering Guide*
