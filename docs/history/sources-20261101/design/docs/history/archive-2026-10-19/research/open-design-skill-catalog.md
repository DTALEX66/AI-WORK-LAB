# Open Design 技能体系完整归纳

> 来源: Open Design v0.21.0 (2026-08-29 本地安装版)
> 归纳到: DESIGN-LAB 项目资料

---

## 一、体系总览

Open Design 的技能体系分为四大仓库：

| 仓库 | 数量 | 用途 | 路径 |
|---|---|---|---|
| **skills/** | 137+ | 技能模板（告诉 AI 怎么做） | `skills/<name>/SKILL.md` |
| **design-systems/** | 151+ | 设计系统（告诉 AI 长什么样） | `design-systems/<name>/DESIGN.md` |
| **design-templates/** | 200+ | 设计模板（可渲染的 HTML 模板） | `design-templates/<name>/` |
| **craft/** | 12 | 工艺规则（通用设计法则） | `craft/*.md` |

---

## 二、Skills 分类 catalogue

### 2.1 品牌与策略

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `brand-extract` | 从 URL/PDF/截图自动提取品牌规范 | ⭐⭐⭐ 极高 |
| `brand-guidelines` | 生成品牌指南文档 | ⭐⭐⭐ 高 |
| `brandkit` | 品牌工具包生成 | ⭐⭐⭐ 高 |
| `design-brief` | 将结构化简报转为 DESIGN.md（8 维解析） | ⭐⭐⭐ 极高 |
| `creative-director` | AI 创意总监（20+方法论，Cannes/D&AD 评审标准） | ⭐⭐⭐ 极高 |
| `brainstorming` | 头脑风暴 | ⭐⭐ 中 |
| `marketing-psychology` | 营销心理学 | ⭐⭐ 中 |

### 2.2 设计与布局

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `canvas-design` | 画布设计 | ⭐⭐⭐ 高 |
| `frontend-design` | 前端设计 | ⭐⭐⭐ 高 |
| `frontend-skill` | 前端技能 | ⭐⭐⭐ 高 |
| `frontend-dev` | 前端开发 | ⭐⭐ 中 |
| `image-to-code-skill` | 图片转代码 | ⭐⭐ 中 |
| `platform-design` | 平台设计 | ⭐⭐ 中 |
| `redesign-skill` | 重设计 | ⭐⭐ 中 |
| `ui-skills` | UI 技能 | ⭐⭐⭐ 高 |
| `ui-ux-pro-max` | UI/UX 高级 | ⭐⭐⭐ 高 |
| `shadcn-ui` | shadcn/ui 组件 | ⭐⭐ 中 |
| `swiftui-design` | SwiftUI 设计 | ⭐ 低 |

### 2.3 动效与视频

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `gsap-core` / `frameworks` / `plugins` / `react` / `scrolltrigger` / `timeline` | GSAP 动效全套 | ⭐⭐ 中 |
| `emilkowalski-motion` | Emil Kowalski 动效风格 | ⭐⭐ 中 |
| `review-animations` | 动画评审 | ⭐⭐ 中 |
| `chat-motion-overlay` | 聊天动效叠加 | ⭐ 低 |
| `video-hyperframes` | HyperFrames 视频 | ⭐⭐ 中 |
| `remotion` | Remotion 视频框架 | ⭐⭐ 中 |
| `sora` | Sora 视频生成 | ⭐ 低 |
| `stitch-loop` / `stitch-skill` | 循环拼接 | ⭐ 低 |
| `vfx-text-cursor` | VFX 文字光标 | ⭐ 低 |

### 2.4 图像生成

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `imagegen` | 图像生成入口 | ⭐⭐⭐ 极高 |
| `imagegen-frontend-web` | Web 前端图像 | ⭐⭐⭐ 高 |
| `imagegen-frontend-mobile` | Mobile 前端图像 | ⭐⭐ 中 |
| `imagen` | Google Imagen | ⭐⭐ 中 |
| `replicate` | Replicate API | ⭐⭐ 中 |
| `fal-generate` / `fal-image-edit` / `fal-video-edit` / `fal-upscale` / `fal-vision` | Fal 全套 | ⭐⭐ 中 |
| `image-enhancer` | 图像增强 | ⭐⭐ 中 |
| `competitive-ads-extractor` | 竞品广告提取 | ⭐⭐ 中 |
| `mockup-device-3d` | 3D 设备模型 | ⭐⭐ 中 |
| `pixelbin-media` | PixelBin 媒体处理 | ⭐ 低 |
| `poster-hero` | 海报 Hero | ⭐⭐ 中 |
| `screenshot` | 截图 | ⭐⭐ 中 |
| `screenshots-marketing` | 营销截图 | ⭐⭐ 中 |
| `full-page-screenshot` | 全页截图 | ⭐⭐ 中 |

### 2.5 演示与文档

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `deck-guizang-editorial` | 杂志风演示 | ⭐⭐⭐ 极高 |
| `deck-swiss-international` | 瑞士国际风演示 | ⭐⭐⭐ 高 |
| `deck-open-slide-canvas` | 开放画布演示 | ⭐⭐ 中 |
| `pptx` / `pptx-generator` / `ppt-keynote` | PPT 全套 | ⭐⭐ 中 |
| `pdf` / `doc` / `docx` | 文档全套 | ⭐⭐ 中 |
| `html-ppt-retro-quarterly-review` | HTML PPT 复古季报 | ⭐⭐ 中 |
| `article-magazine` | 文章杂志 | ⭐⭐ 中 |
| `data-report` | 数据报告 | ⭐⭐ 中 |
| `release-notes-one-pager` | 一页发布说明 | ⭐ 低 |

### 2.6 电商与营销

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `ecommerce-image-workflow` | 电商图像工作流 | ⭐⭐ 中 |
| `ad-creative` | 广告创意 | ⭐⭐ 中 |
| `copywriting` | 文案写作 | ⭐⭐ 中 |
| `faq-page` | FAQ 页面 | ⭐ 低 |
| `login-flow` | 登录流程 | ⭐ 低 |
| `paywall-upgrade-cro` | 付费升级 CRO | ⭐ 低 |
| `resume-modern` | 现代简历 | ⭐ 低 |

### 2.7 社交媒体

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `card-twitter` / `social-x-post-card` | X/Twitter 卡片 | ⭐ 低 |
| `card-xiaohongshu` | 小红书卡片 | ⭐ 低 |
| `social-reddit-card` | Reddit 卡片 | ⭐ 低 |
| `social-spotify-card` | Spotify 卡片 | ⭐ 低 |
| `gif-sticker-maker` | GIF 贴纸制作 | ⭐ 低 |
| `slack-gif-creator` | Slack GIF 制作 | ⭐ 低 |

### 2.8 3D 与着色器

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `threejs` | Three.js | ⭐⭐ 中 |
| `shader-dev` | 着色器开发 | ⭐⭐ 中 |
| `fal-3d` | Fal 3D | ⭐⭐ 中 |
| `algorithmic-art` | 算法艺术 | ⭐ 低 |
| `d3-visualization` | D3 可视化 | ⭐ 低 |
| `hand-drawn-diagrams` | 手绘图表 | ⭐ 低 |

### 2.9 音频与音乐

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `venice-audio-music` / `venice-audio-speech` | Venice 音频/语音 | ⭐ 低 |
| `ai-music-album` | AI 音乐专辑 | ⭐ 低 |
| `speech` | 语音 | ⭐ 低 |

### 2.10 工具与调试

| Skill | 描述 | 对本项目价值 |
|---|---|---|
| `screenshot` | 截图 | ⭐⭐ 中 |
| `export-download-debugging` | 导出下载调试 | ⭐⭐ 中 |
| `library-curator` | 库策展 | ⭐ 低 |
| `plan-design-review` | 计划设计评审 | ⭐⭐ 中 |
| `pr-feedback-quality-gate` | PR 反馈质量门 | ⭐⭐ 中 |
| `reference-design-contract` | 参考设计合同 | ⭐⭐ 中 |

---

## 三、Design Systems 分类 catalogue

### 3.1 科技/SaaS（与星云科技最相关）

| System | 风格 | 对本项目参考价值 |
|---|---|---|
| `linear-app` | 工程优先极简，单色+强调色，4px 倍数间距 | ⭐⭐⭐ 极高 |
| `vercel` | 高对比编辑风，黑白+单色，Inter 字体 | ⭐⭐⭐ 极高 |
| `stripe` | 克制科技编辑风，大量留白，Sohne 字体 | ⭐⭐⭐ 极高 |
| `cursor` | 开发者工具风 | ⭐⭐⭐ 高 |
| `cloudflare-kumo` | Cloudflare 风格 | ⭐⭐⭐ 高 |
| `clickhouse` | ClickHouse 风格 | ⭐⭐ 中 |
| `cohere` | Cohere AI 风 | ⭐⭐ 中 |
| `gemini` | Google Gemini | ⭐⭐ 中 |
| `anthropic-claude` | Claude 风格 | ⭐⭐ 中 |
| `github` | GitHub 风 | ⭐⭐ 中 |
| `notion` | Notion 风 | ⭐⭐ 中 |
| `figma` | Figma 风 | ⭐⭐ 中 |
| `arc` | Arc 浏览器风 | ⭐⭐ 中 |
| `vercel` | Vercel 风 | ⭐⭐⭐ 极高 |
| `linear-app` | Linear 风 | ⭐⭐⭐ 极高 |
| `expo` | Expo 风 | ⭐⭐ 中 |
| `docker` | Docker 风 | ⭐ 低 |
| `cohere` | Cohere 风 | ⭐⭐ 中 |
| `binance` | 币安风 | ⭐ 低 |
| `coinbase` | Coinbase 风 | ⭐ 低 |

### 3.2 消费/品牌

| System | 风格 | 对本项目参考价值 |
|---|---|---|
| `apple` | 消费级精致，SF Pro，电影级图片 | ⭐⭐⭐ 极高 |
| `airbnb` | 友好温暖 | ⭐⭐ 中 |
| `spotify` | 音乐活力 | ⭐⭐ 中 |
| `duolingo` | 游戏化 | ⭐ 低 |
| `bmw` / `bmw-m` | 汽车高端 | ⭐⭐ 中 |
| `bugatti` | 超跑奢华 | ⭐ 低 |
| `tesla` | 特斯拉风 | ⭐⭐ 中 |
| `nike` | Nike 运动 | ⭐⭐ 中 |
| `patagonia` | 户外环保 | ⭐ 低 |

### 3.3 企业/专业

| System | 风格 | 对本项目参考价值 |
|---|---|---|
| `corporate` | 企业风 | ⭐⭐⭐ 高 |
| `enterprise` | 企业级 | ⭐⭐⭐ 高 |
| `professional` | 专业风 | ⭐⭐⭐ 高 |
| `premium` | 高端风 | ⭐⭐⭐ 高 |
| `elegant` | 优雅风 | ⭐⭐ 中 |
| `luxury` | 奢华风 | ⭐⭐ 中 |

### 3.4 视觉方向

| System | 风格 | 对本项目参考价值 |
|---|---|---|
| `brutalism` | 粗野主义 | ⭐⭐ 中 |
| `editorial` | 编辑风 | ⭐⭐⭐ 高 |
| `minimal` | 极简风 | ⭐⭐⭐ 极高 |
| `monochrome` | 单色 | ⭐⭐ 中 |
| `clean` | 干净风 | ⭐⭐⭐ 高 |
| `dark` | 暗色 | ⭐⭐ 中 |
| `dramatic` | 戏剧性 | ⭐⭐ 中 |
| `expressive` | 表现力 | ⭐⭐ 中 |
| `fantasy` | 奇幻 | ⭐ 低 |
| `playful` | 趣味 | ⭐ 低 |

---

## 四、Craft 工艺规则

| 文件 | 内容 | 价值 |
|---|---|---|
| `anti-ai-slop.md` | 反 AI 痕迹清单 | ⭐⭐⭐ 极高 |
| `typography.md` | 排版规则 | ⭐⭐⭐ 极高 |
| `typography-hierarchy.md` | 排版层次 | ⭐⭐⭐ 极高 |
| `typography-hierarchy-editorial.md` | 编辑排版层次 | ⭐⭐⭐ 高 |
| `color.md` | 色彩规则 | ⭐⭐⭐ 极高 |
| `animation-discipline.md` | 动效规则 | ⭐⭐ 中 |
| `accessibility-baseline.md` | 无障碍基线 | ⭐⭐⭐ 极高 |
| `laws-of-ux.md` | UX 法则 | ⭐⭐⭐ 高 |
| `rtl-and-bidi.md` | RTL/Bidi 规则 | ⭐⭐ 中 |
| `form-validation.md` | 表单验证 | ⭐ 低 |
| `state-coverage.md` | 状态覆盖 | ⭐ 低 |
| `FUTURE_SECTIONS.md` | 未来扩展 | 参考 |

---

## 五、Anti-AI-Slop 规则（核心）

来自 `craft/anti-ai-slop.md`，这是 Open Design 最核心的视觉质量保障：

### 绝对禁止清单

| 禁止项 | 说明 |
|---|---|
| 紫色/紫罗兰渐变背景 | AI 最爱，一眼假 |
| Emoji 功能图标（✨🚀🎯） | 不专业 |
| 左侧边框圆框卡片 | Claude 风格模板 |
| 手绘 SVG 人/脸/风景 | 廉价感 |
| Inter/Roboto/Arial 作为 Display 字体 | Body 字体做标题 |
| 编造的数据（"10x faster"、"99.9% uptime"） | 无来源 |
| 填充文案（"Feature One / Feature Two"） | Lorem ipsum |
| 每个标题旁边都有图标 | 过度装饰 |
| 每个背景都有渐变 | 视觉疲劳 |
| 暖米色/奶油/桃色/粉/橙棕色背景 | 除非品牌要求 |
| 暴露设计师设置/视口选择器/平台切换 | 不是 App UI |

### 正面规则

| 规则 | 说明 |
|---|---|
| 每个版面最多 2 种字体 | Mono 作为工具字体不计 |
| 强调色最多出现 2 次/屏 | 克制使用 |
| 不要用 Body 字体做 Display | 层次区分 |
| 从 Domain 选择背景色 | 不选通用暖色 |
| 有真实数据，无假指标 | 诚实占位 |
| 每屏一个视觉焦点 | 层次清晰 |

---

## 六、5 维自检雷达

Open Design 官方设计评审标准：

| 维度 | 问题 | 分值 |
|---|---|---|
| **Philosophy** | 视觉姿态是否符合要求（编辑/极简/粗野）？还是回到了默认偏好？ | 1-5 |
| **Hierarchy** | 视线是否落在每屏一个明显位置？还是都在竞争？ | 1-5 |
| **Execution** | 排版/间距/对齐/对比度 — 正确还是凑合？ | 1-5 |
| **Specificity** | 每个词/数字/图片都针对此简报？还是填充物/通用数据？ | 1-5 |
| **Restraint** | 一个强调色最多用两次，一个决定性点缀 — 还是三个竞争元素？ | 1-5 |

**合格线：每维 ≥ 3/5**

---

## 七、DESIGN.md 9 段式模板

```markdown
# [Project] Design System

## 1. Visual Theme & Atmosphere
- Mood:
- Feel:
- References:

## 2. Color Palette & Roles
- Background:
- Surface:
- Text primary:
- Text secondary:
- Accent:
- Accent hover:

## 3. Typography Rules
- Display:
- Body:
- Mono:

## 4. Component Stylings
- Buttons:
- Cards:
- Inputs:

## 5. Layout Principles
- Max width:
- Grid:
- Section spacing:
- Content padding:

## 6. Depth & Elevation
- Shadows:
- Borders:

## 7. Do's and Don'ts
- DO:
- DON'T:

## 8. Responsive Behavior
- Breakpoints:
- Mobile:
- Tablet:
- Desktop:

## 9. Agent Prompt Guide
- 对 AI 的额外约束
```

---

## 八、星云科技 DESIGN.md 推荐基础

基于 151 个设计系统对比，推荐参考方向：

| 参考系统 | 原因 |
|---|---|
| `linear-app` | B2B 科技企业首选，信息密度适中 |
| `vercel` | 高对比编辑风，适合展示 |
| `stripe` | 克制科技感，信任信号 |
| `cursor` | 开发者工具，与科技品牌契合 |

---

## 九、如何整合到 DESIGN-LAB

### 推荐执行

1. **为星云科技创建 DESIGN.md** — 基于 9 段式模板
2. **创建 culture-wall-designer SKILL.md** — 含 P0 Checklist
3. **安装 brand-extract + creative-director** — 自动品牌提取
4. **创建项目专属 design-system** — 可复用
5. **配置 memory hooks** — 记住"不要紫渐变"等规则

---

*文件: docs/research/open-design-skill-catalog.md*
*数据来源: Open Design v0.21.0 本地安装*
*共 137+ Skills / 151+ Design Systems / 12 Craft / 200+ Templates*
