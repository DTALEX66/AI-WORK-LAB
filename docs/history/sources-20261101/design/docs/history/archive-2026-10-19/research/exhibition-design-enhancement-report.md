# 文化墙展厅设计增强调研报告

## 一、Open Design 官方资源

### 1.1 现有空间/展陈设计技能

Open Design 已内置两个空间/展陈设计技能：

| 技能 | 路径 | 能力 |
|---|---|---|
| `spatial-exhibition-designer` | `adapters/hosts/open-design/expert-suite/skills/spatial-exhibition-designer/SKILL.md` | 文化墙、展厅、展陈、品牌体验空间、导视、2D 立面与 3D 空间表达 |
| `spatial-exhibition-director` | `plugins/spatial-exhibition-director/SKILL.md` | 生成 culture wall、exhibition hall、showroom、brand center 的 brief |

### 1.2 插件市场数据

- **Skills**: 276+ droppable SKILL.md bundles
- **Design Systems**: 150+ portable DESIGN.md systems
- **总插件数**: 460+
- **支持 16 coding agents**: Claude Code, Codex, Cursor, Gemini CLI, OpenCode, Qwen, Hermes, etc.

### 1.3 关键文档

- `docs/plugins-spec.md` - 插件规范
- `docs/skills-protocol.md` - 技能协议
- `design-systems/` - 设计系统目录

---

## 二、开源设计工具栈

### 2.1 核心工具对比

| 工具 | 许可 | 最佳用途 | 与展厅设计相关性 |
|---|---|---|---|
| **Blender** | GPL | 3D 全流程：建模/雕刻/动画/渲染/视频编辑/合成 | ⭐⭐⭐⭐⭐ 展厅 3D 建模、灯光渲染、动画 |
| **Penpot** | MPL-2.0 | Figma 替代品，SVG 原生，实时协作，支持 MCP | ⭐⭐⭐⭐ UI/UX 展厅界面、导视系统 |
| **Inkscape** | GPL | 矢量编辑，SVG 原生，可导出 PDF/EPS/PNG | ⭐⭐⭐⭐⭐ 展厅平面图、矢量图形、导视标识 |
| **Krita** | GPL | 数字绘画，100+ 画笔，支持 AI Diffusion | ⭐⭐⭐⭐ 展厅视觉素材创作 |
| **GIMP** | GPL | 图像编辑，3.2 新增非破坏性图层 | ⭐⭐⭐ 图像修调、材质处理 |
| **Scribus** | GPL | 桌面出版，CMYK，PDF/X 输出 | ⭐⭐⭐⭐ 展板排版、印刷规范 |
| **Excalidraw** | MIT | 白板、流程图、架构草图 | ⭐⭐⭐ 展厅动线规划 |
| **draw.io** | MIT | 流程图、系统图 | ⭐⭐⭐ 展厅信息架构 |
| **OBS Studio** | GPL | 录屏、直播、场景切换 | ⭐⭐⭐ 数字展厅多媒体 |
| **Darktable** | GPL | 摄影后期，非破坏性 RAW 处理 | ⭐⭐⭐ 展厅摄影素材处理 |

### 2.2 Blender 详细能力（展厅核心）

```
Blender 5.2 LTS 新增:
- 纹理画笔增强
- Online Essentials 资源库
- 改进的 Cycles 渲染器

展厅应用:
- 3D 空间建模（墙体、天花板、地板、展柜）
- 材质系统（金属、玻璃、木材、亚克力、LED）
- 灯光系统（区域光、IES 配置文件、HDRI）
- 摄像机动画（参观动线预览）
- 渲染输出（EEVEE 实时 / Cycles 照片级）
- 视频编辑（展厅宣传片）
- 物理模拟（布料、流体）
```

### 2.3 Inkscape 详细能力（导视核心）

```
展厅应用:
- SVG 矢量展板设计
- 精确尺寸控制（mm 级）
- 文字转路径（输出安全）
- 图层管理（展板分层）
- PDF 导出（含出血）
- 对齐与分布（模块化布局）
- 色彩管理（CMYK 转换）
```

---

## 三、AI 设计增强工具

### 3.1 AI 图像生成工具对比

| 工具 | 类型 | 优势 | 劣势 | 展厅适用 |
|---|---|---|---|---|
| **ComfyUI** | 开源/本地 | 节点化工作流、最快 SDXL (~8s)、ControlNet/IP-Adapter | 学习曲线陡峭 | ⭐⭐⭐⭐⭐ 批量生成展厅效果图、材质 |
| **InvokeAI** | 开源/本地 | Photoshop 风格画布、inpainting/outpainting、易上手 | VRAM 占用中等 | ⭐⭐⭐⭐⭐ 展厅局部修改、扩展 |
| **Krita AI Diffusion** | 开源/插件 | 绘画+AI 无缝集成、ComfyUI 后端 | 依赖 ComfyUI 服务器 | ⭐⭐⭐⭐ 展厅视觉创作 |
| **Forge** | 开源/本地 | VRAM 效率最高 (~8-9GB SDXL) | 功能较少 | ⭐⭐⭐⭐ 低显存展厅渲染 |
| **Adobe Firefly** | 商业/云端 | 商业安全、与 Adobe 生态集成 | 需联网、订阅费 | ⭐⭐⭐⭐ 商业展厅项目 |
| **ExpoBooth.ai** | 商业/AI 服务 | AI 展位设计专用、60 秒出图 | 付费、通用性差 | ⭐⭐⭐⭐⭐ 展位快速概念 |
| **RENDERCAD** | 商业/AI 服务 | CAD 截图→照片级渲染、60 秒 | 付费、非开源 | ⭐⭐⭐⭐ 展厅效果图 |
| **MyAIArt** | 免费/云端 | AI 展览生成器、floor plan+booth | 通用 AI、精度有限 | ⭐⭐⭐ 快速展厅概念 |

### 3.2 ComfyUI 展厅工作流

```
推荐工作流:
1. 输入: 展厅平面图 (Inkscape 导出 SVG → PNG)
2. ControlNet Depth: 空间深度控制
3. ControlNet Canny: 边缘控制
4. IP-Adapter: 风格参考
5. KSampler: SDXL / FLUX 生成
6. Upscale: 4K 放大
7. 输出: 展厅效果图

推荐模型:
- SDXL: Juggernaut XL, RealVisXL
- FLUX: dev/schnell (需 16GB+ VRAM)
- 展厅专用 LoRA: Interior Design, Architecture
```

---

## 四、展厅设计专业规范

### 4.1 中国国家标准

| 标准 | 内容 | 关键参数 |
|---|---|---|
| **GB 50034-2024** | 建筑照明设计标准 | 替代 2013，增加照明舒适度 |
| **GB 50034-2013** | 建筑照明设计标准 | 展厅照度、显色指数 |
| **GB/T 18883-2022** | 室内空气质量标准 | 展厅空气质量 |
| **GB 50736-2012** | 民用建筑供暖通风与空气调节设计规范 | 展厅温湿度 |

### 4.2 照度标准（GB 50034 + CIE）

| 场所/材料 | 推荐照度 (lux) | 年曝光限制 |
|---|---|---|
| 极敏感（纺织品、纸张、照片、水彩） | 50 lux | ≤ 30,000 lux·h/年 |
| 中等敏感（油画、皮革、象牙） | 150-200 lux | ≤ 60,000 lux·h/年 |
| 稳定材料（金属、石材、陶瓷） | 300 lux | 无限制 |
| **展厅一般照明** | **200-500 lux** | — |
| **文化墙立面** | **150-300 lux** | — |
| **导视标识** | **200-500 lux** | — |
| **互动触摸屏** | 300-500 lux | — |

### 4.3 照明设计规范

#### 光源参数
- **CRI (显色指数)**: ≥ 90（展厅），≥ 95（博物馆级）
- **R9 (红色显色)**: ≥ 50（展厅），≥ 95（博物馆级）
- **色温**: 2700K-4000K（暖白-中性白）
- **UV 辐射**: < 75 μW/lm
- **IR 辐射**: 最小化

#### 照明方式
- **一般照明**: 均匀照度 200-500 lux
- **重点照明**: 立面 150-300 lux，30° 入射角
- **洗墙照明**: 灯具距墙 1/3-1/6 墙高
- **展柜照明**: 内部 50-200 lux（敏感物品）
- **导视照明**: 背光/侧光，200-500 lux

#### 智能照明控制
- **DALI-2** 骨干 + **Casambi** 无线 + **DMX** 场景
- 恒照度调光：日光传感器 + 人体感应
- 色温可调：2700K-5000K (IEC 62386-209 DT8)

### 4.4 材质选择规范

| 材料 | 特性 | 适用场景 | 加工方式 |
|---|---|---|---|
| **亚克力 (PMMA)** | 多色、耐候性中等、可激光切割 | 展板、标识、展柜 | 激光切割/丝印/数码打印/热弯 |
| **铝** | 轻质、耐腐蚀、耐用 | 框架、面板、标识 | 粉末涂层/阳极氧化/数码打印 |
| **不锈钢** | 高端、极耐用、耐腐蚀 | 高端室内外 | 拉丝/抛光/喷涂 |
| **PVC foam board** | 轻量、低成本、低耐用 | 临时/低成本展板 | 数码打印/UV 打印 |
| **玻璃/陶瓷** | 高端、耐用、易清洁 | 触觉标识、展柜 | 丝印/烤花 |
| **木材** | 温暖、自然、需处理 | 文化墙、接待台 | 雕刻/路由/贴膜 |
| **LED 灯箱** | 均匀发光、可更换画面 | 大型展板、背景墙 | 数码打印/UV 打印 |

### 4.5 导视设计规范

#### 观看距离与字体大小
| 观看距离 | 最小字高 | 适用场景 |
|---|---|---|
| < 1m | 10mm | 说明文字 |
| 1-3m | 25mm | 区域标题 |
| 3-6m | 50mm | 主标题 |
| 6-10m | 100mm | 展厅标识 |
| > 10m | 150mm+ | 建筑标识 |

#### 导视设计原则
1. **远读/中读/近读** 三级信息层次
2. **色彩对比度**: WCAG AA（4.5:1），AAA（7:1）
3. **字体选择**: 无衬线体（中文：思源黑体、苹方）
4. **盲文/触觉**: 关键标识需包含
5. **照明**: 避免眩光，30° 入射角

### 4.6 文化墙设计规范

#### 空间尺度
- **层高**: 2.4m-4.5m（常规），4.5m+（高端）
- **观看距离**: 1.5m-3m（主立面），3m-6m（次立面）
- **通道宽度**: 主通道 ≥ 2.4m，次通道 ≥ 1.8m

#### 设计原则
1. **叙事动线**: 起承转合，有节奏感
2. **视觉锚点**: 每 3-5m 一个视觉焦点
3. **留白**: 信息密度 ≤ 40%，呼吸感
4. **模块化**: 可更换、可升级
5. **无障碍**: 轮椅可及高度 0.9m-1.2m

#### 常见布局系统
- **时间轴 ribbon**: 历史/进程/成就
- **模块化网格**: 价值观/荣誉/团队/产品
- **Hero statement**: 大标语 + 证明模块
- **博物馆条**: 标题/文物/说明/序列
- **分层浮雕**: 2D 图形 + 立体字 + 灯光
- **互动墙**: QR/LED/触摸/旋转内容

---

## 五、开源项目推荐

### 5.1 Exhibition Wall Mockup Maker

- **仓库**: `tiagomartinspinto/exhibitionwallmockupmaker`
- **许可**: MIT
- **能力**:
  - 浏览器端展厅规划
  - 2D 墙体布局 + 3D 预览
  - 拖拽编辑、标尺、对齐
  - PDF 导出（安装图、标签、包装）
  - 毫米级精度
  - 本地存储 + JSON 保存

### 5.2 其他相关项目

| 项目 | 用途 | 许可 |
|---|---|---|
| **OpenAssetIO** | 资产引用管理（替代硬编码路径） | Apache-2.0 |
| **OpenTimelineIO** | 时间线交换（动效/视频） | BSD-3-Clause |
| **OpenColorIO** | 色彩管理 | BSD-3-Clause |
| **MaterialX** | 3D 材质交换 | Apache-2.0 |
| **OpenUSD** | 3D 场景层次 | Apache-2.0 |
| **glTF** | 轻量 3D 交付 | 开放规范 |

---

## 六、AI 增强展厅设计工作流

### 6.1 完整工作链

```
Brief → Design IR → 3D 建模 (Blender) → AI 渲染 (ComfyUI) → 展板设计 (Inkscape) → 导视系统 → 输出 (PDF/PNG/MP4)
```

### 6.2 推荐工具链

| 阶段 | 工具 | 输出 |
|---|---|---|
| 概念 | Open Design + spatial-exhibition-designer | Brief + 方向 |
| 3D 空间 | Blender | .blend + 渲染图 |
| AI 效果图 | ComfyUI + ControlNet | 展厅效果图 |
| 展板矢量 | Inkscape | SVG + PDF |
| 导视系统 | Inkscape + 字体规范 | 标识文件 |
| 渲染 | Blender Cycles / RENDERCAD | 照片级渲染 |
| 视频 | Blender VSE + FFmpeg | 展厅动画 |
| 交互 | Penpot / HTML | 数字展厅 |

### 6.3 Open Design 插件增强建议

基于调研，建议为 Open Design 开发以下插件：

1. **spatial-exhibition-pro** - 增强版展厅设计技能
   - 集成 Blender 3D 建模指令
   - 集成 ComfyUI 渲染指令
   - 集成 GB 50034 照度标准
   - 集成材质选择规范

2. **wayfinding-designer** - 导视系统设计技能
   - 字体大小自动计算（基于观看距离）
   - 色彩对比度检查（WCAG AA/AAA）
   - 盲文/触觉标识支持

3. **exhibition-lighting-designer** - 照明设计技能
   - 照度计算（基于 GB 50034）
   - 灯具选型（基于 CRI/色温/UV）
   - 年曝光量计算（博物馆级）

---

## 七、总结

### 可立即使用的资源
1. **Open Design 内置**: spatial-exhibition-designer + spatial-exhibition-director
2. **开源工具**: Blender (3D) + Inkscape (矢量) + Krita (绘画) + Scribus (排版)
3. **AI 增强**: ComfyUI (效果图) + InvokeAI (局部修改)
4. **开源项目**: Exhibition Wall Mockup Maker (展厅规划)

### 需要安装的依赖
- Blender 5.2+ (3D 渲染)
- Inkscape 1.3+ (矢量设计)
- Krita 5.2+ (数字绘画 + AI Diffusion)
- ComfyUI (AI 图像生成)

### 需要遵循的标准
- GB 50034-2024 (照明设计)
- CIE 157:2004 (博物馆照明)
- WCAG 2.1 AA (无障碍)
- ICOM-CC (曝光预算)

---

*调研时间: 2026-08-27*
*调研范围: Open Design 官方、开源工具、AI 设计工具、展厅设计规范*
