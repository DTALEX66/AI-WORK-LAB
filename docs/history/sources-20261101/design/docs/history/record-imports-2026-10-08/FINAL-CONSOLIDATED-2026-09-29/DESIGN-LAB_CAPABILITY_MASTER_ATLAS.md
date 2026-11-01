# 能力总图谱

> 只读审计 / 2026-09-29 / current main `010f6a57610214fa41651861e00319f88a2f49a4`。本文是审计与候选方案，不是新 Authority，也不是第二份可编辑任务账本。历史完整性：**未完成**；Windows 实机复测：**本轮未执行**。

## 分类语义

CURRENT=当前产品范围；INTEGRATED=结构/资料已吸收，不等于运行；ADOPT=建议吸收；EVALUATE=需比较；SIDECAR=外部进程；HOST_ADAPTER=设计宿主边界；MODEL_PROVIDER=推理能力；TOOL_PROVIDER=特定工具；ALGORITHM_DONOR=算法来源；UX_DONOR=交互参考；REFERENCE=参考；BLOCKED=条件缺失；DEFERRED=后置；REJECT_CORE=明确不进入核心。分类与E等级独立。

下表的E等级是可支持的范围性结论，不是整族统一认证。当前能力资格必须再核对每个适配器版本、输入输出、subject SHA、环境和 artifacts。所有历史未实现项保留，不因排期后置删除。


| 能力族 | 保留范围 | 分类 | 证据范围 | 入口 | 下一缺口 |
| --- | --- | --- | --- | --- | --- |
| Design Intelligence | Brief/计划/Design IR | CURRENT | E1；部分受控链E2 | native plans + object model | 真实参考到可修改对象计划 |
| Reference Research | 引用/授权/来源 | CURRENT | E1；部分导入E2 | references + assets | 真实检索与引用、授权闭环 |
| Style / Visual DNA | 风格谱系/配方 | INTEGRATED | E1 | visual-quality research | 真实客户DNA与非模仿审查 |
| Direction | 方向候选与选择 | CURRENT | E2受控UI范围 | workbench + API | 方向版本与成品可追溯 |
| Design System | 系统绑定与DTCG | CURRENT | E1/E2子集 | interop/dtcg.py | token编辑/版本/发布回滚 |
| Typography | 字体/脚本/可读性 | INTEGRATED | E1 | 24-axis model | 字体实际观察、权利及缺字预检 |
| Color | 配色/比例/色彩空间 | INTEGRATED | E1 | rubrics/profiles | ICC/CMYK/实物打样验证 |
| Layout | 层级/版式 | INTEGRATED | E1 | methods | 可编辑对象布局回读 |
| Composition | 焦点/平衡 | INTEGRATED | E1 | quality model | 盲评和任务匹配 |
| Grid | 栅格/响应式 | INTEGRATED | E1 | methods/UI | 跨尺寸与语言实测 |
| Image Direction | 摄影/材质/光照 | INTEGRATED | E1 | quality model | 与Brief一致性、anti-artifact验收 |
| Brand | 品牌策略/视觉系统 | CURRENT | E1 | domain/method packs | 品牌全套真实案例 |
| Graphic / Editorial | 海报/出版排版 | CURRENT | E1 | domain/method packs | 多页链接与字体交付 |
| UI / UX | 界面/交互系统 | CURRENT | E1；workbench自身E2 | packs + workbench | Figma/Penpot可编辑往返 |
| E-commerce | 商品图/营销变体 | ADOPT | E0/E1方法 | domain pool | 授权商品素材和尺寸批量链 |
| Packaging | 包装/刀模/印前 | EVALUATE | E1方法 | quality/preflight plans | 专业供应商规格与打样 |
| Exhibition / Spatial | 空间/展陈 | DEFERRED | E0/E1历史方法 | historical pool | 尺度/材质/施工交付 |
| 3D / VFX | 场景/材质/渲染 | DEFERRED | E1适配规划 | DL-R5-020 | 真实Blender可编辑回读 |
| Motion | 动画/时间/节奏 | DEFERRED | E1规划 | DL-R5-025 | 时序可编辑交付 |
| Video | 剪辑/字幕/轨道 | DEFERRED | E1规划 | DL-R5-019 | Premiere工程重开与媒体链接 |
| Game Visual | 视觉资产/atlas | CURRENT | E1/E2 fixture | MiniGame node gate | 真实游戏资产交付；非游戏引擎 |
| Production | 生产规格/依赖 | CURRENT | E1 | native delivery | 整链交付与接收 |
| Preflight | 字体/链接/色彩/尺寸 | CURRENT | E1/E2检查子集 | native bundles | 从声明升级实际观察 |
| Editable Delivery | 编辑源文件/BOM | CURRENT | E1/E2导出子集 | native_delivery.py | 宿主重开、改字、依赖无损 |
| Rights / Licensing | 授权与使用范围 | CURRENT | E1 | rights contracts | 真实权利证据和人审 |
| Jury / Critique | 多角色专业评审 | INTEGRATED | E1 | quality core | 独立人审E4，VLM仅建议 |
| Accessibility | 产品及设计可访问性 | ADOPT | E1/E2有限UI检查 | W14 + axe候选 | 键盘/读屏/IME/高对比 |
| Anti-AI-artifact Quality | 结构/文字/材质伪影 | INTEGRATED | E1 | quality axes | 真实失败集与局部修正 |
| Asset Provenance | 来源/版本/转换链 | CURRENT | E1/E2子集 | assets/bundles | 完整引用与派生追踪 |
| Host Adapter | 宿主执行/回读/回滚 | HOST_ADAPTER | E1/E2；历史实机另列 | PS/AI adapters | 当前exactSHA真实项目 |
| Model Provider | 模型资格/能力 | MODEL_PROVIDER | E0/E1；个别历史受控 | qualification registry | 具体硬件模型版本基准 |
| Rendering | 宿主渲染/色彩管理 | TOOL_PROVIDER | E1规划/局部工具 | Blender/OCIO pool | 跨宿主一致性 |
| Image Generation | 可选图像生成 | MODEL_PROVIDER | E1；非模型Comfy历史E3范围 | Comfy/H3/Qwen | 真实模型质量/资源/取消基准 |
| Video Generation | 可选视频生成 | MODEL_PROVIDER | E0/E1 | Wan/Comfy pool | 时序一致/显存/可编辑边界 |
| 3D Generation | 可选3D生成 | MODEL_PROVIDER | E0/E1 | Hunyuan pool | 许可、拓扑、材质及场景合并 |
| MCP / Tool Adapter | 设计工具协议/诊断 | TOOL_PROVIDER | E1/E2协议子集 | adapter policy | 权限/超时/取消/日志脱敏 |

## 正式产品长期蓝图

基础对象保持 Project、Brief、Reference、Direction、DesignSystem、DesignIR、Asset、DomainPack、Method、JuryReport、Rights、Preflight、EditableHandoff/BOM/Provenance 等契约关系；新增 UI 不私建语义重复对象。专业域通过 packs 与 host adapters 扩展，模型与工具可替换。KnowledgeCandidate 是审批后的导出对象，不是把整个项目交给知识系统。

能力成功定义为“做出可继续修改、可验证生产条件、可追踪授权的设计成果”。高评分与生成漂亮预览仅覆盖其中一部分。
