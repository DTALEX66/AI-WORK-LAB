# 操作设计软件的开源库/脚本生态调研（DESIGN-LAB）

> 调研日期：2026-08-18 · 方法：web_search 逐项核实（仓库/开发者、许可证、能力、维护状态）
> 适配判断口径：**可直接吸收源码**（宽松许可 + 轻量/纯实现，可 vendored）；**做 adapter**（E0 契约：外部进程/CLI/网络 API，平台中立原则下 DESIGN-LAB 只做适配层）；**仅参考**（许可或平台绑定导致无法吸收/适配价值有限）。

## 总表

| 项目 | 开发者 | 许可证 | 操作能力 | 维护 | 适配判断 |
|---|---|---|---|---|---|
| uxp-toolkit | bubblydoo | MIT | 构建 Photoshop UXP 插件的 TS/JS 工具集：UI 组件、PS API 封装、清单生成、watch/打包 | 维护中（npm @bubblydoo/uxp-toolkit，有文档站） | 仅参考——UXP 是 Adobe 私有平台、运行在 PS 进程内，无法 vendored；至多做 adapter 生成/驱动 UXP 插件 |
| ExtendScript（Adobe 官方脚本） | Adobe | 专有（脚本语言官方提供；社区脚本各自许可） | PS/AI 旧版脚本引擎（.jsx/.jsxbin）：DOM 操作文档/图层/文字/导出 | 已停止开发，Adobe 转向 UXP | 仅参考——专有运行时，DESIGN-LAB 不内嵌；平台绑定，无 E0 契约价值 |
| aio-lib-photoshop-api | Adobe（官方 I/O SDK） | Apache-2.0 | 云 Photoshop API：服务端 PSD 图层/文本操作、Firefly 渲染、导出 | 维护中（github.com/adobe/aio-lib-photoshop-api） | 仅参考——网络云服务（需 Adobe 账号/token），可做 adapter 但收益受外部依赖限制 |
| adobepy | dcc-mcp 组织 | [未核实] | Python 与 Adobe 桌面应用通信运行时（MCP adapter，经 UXP/ExtendScript 桥接） | 新项目，维护中 | [未核实]细节；方向为 MCP，与 DESIGN-LAB 本地验证器无关，仅参考 |
| figma-js | jemgold（Jonathan Goldman） | MIT | Figma REST API 的 Node 封装 + TS 类型：读文件/节点、导出图片、评论等 | 低维护——最后发布 1.16.1-0（约 2023），depscope 健康分 47/100 | 做 adapter——纯 JS 轻量、MIT 可 vendored；但 Figma API 需网络+token，适合 E0 契约适配（文件读取/导出） |
| @figma/rest-api-spec | Figma（官方） | Apache-2.0 | Figma REST API 的 OpenAPI 规范与 TS 类型（figma/rest-api-spec） | 维护中（官方持续更新版本） | 可直接吸收源码——纯规范+类型、无运行时依赖，天然可生成 E0 契约验证器 |
| Figma Plugin API / plugin-samples | Figma（官方） | 官方文档+样例仓库 | 插件运行于 Figma 沙箱（plugin-sandbox），操作画布/节点/导出 | 维护中 | 仅参考——平台私有沙箱，无法 vendored；插件生态只做参考 |
| Blender Python API（bpy） | Blender Foundation | GPL-2.0-or-later | Blender 内嵌完整 Python API：headless 建模/材质/渲染/导出（blender --background --python） | 活跃维护（Blender 4.x LTS 节奏） | 做 adapter——bpy 只能在 Blender 进程内运行，走 subprocess/CLI 契约；GPL 传染不可 vendored，平台中立原则下仅外部调用 |
| bpy_wrapper | mechanicalflower | [未核实] | bpy 的封装/包装库（简化 Blender 脚本） | [未核实] | [未核实]细节，仅参考 |
| Inkscape（CLI） | Inkscape 项目（社区） | GPL-2.0-or-later | CLI 批处理：SVG→PNG/PDF 导出、转换、路径操作（inkscape --export-*） | 活跃维护（1.x 系列） | 做 adapter——headless CLI 契约，子进程调用不受 GPL 影响；验证器不依赖它，仅格式操作走 adapter |
| CairoSVG | Kozea | LGPL-3.0 | Python 渲染 SVG→PNG/PDF/PS（纯 Python 逻辑 + cairocffi 绑定原生 cairo） | 维护中（2.7.x） | 做 adapter / 仅参考——LGPL 可 vendored 但需遵守条款，且依赖原生 cairo，与验证器仅标准库冲突，渲染只能走 adapter |
| svglib | 原作者 Dinu Gherman（deeplook），现维护 Claude Paroz（claudep） | LGPL-3.0 | Python 纯实现：SVG→reportlab 图形对象→PDF/PNG | 中低维护（1.5.x 后节奏放缓） | 仅参考——纯 Python 但 LGPL-3.0 + 强依赖 reportlab；SVG 解析思路对标准库验证器有借鉴价值，不直接 vendored |
| svgo | svg/svgo 组织（核心 Kir Belevich） | MPL-2.0 | Node.js SVG 优化器：路径简化、去冗余、清理、格式化（CLI+库） | 活跃维护（v4.0.0 已发布） | 做 adapter——CLI/JS 契约；MPL-2.0 文件级许可可 vendored（需保留源文件可得性），验证器无需吸收 |
| resvg | 原作者 RazrFalcon，现托管 linebender | MPL-2.0 → 双许可 MIT/Apache-2.0（v0.45.1 起，linebender 2024-10 公告 + issue #838） | Rust SVG 渲染器：高质量 SVG→PNG（SVG 标准支持全） | 活跃维护（linebender 接手后持续发布 0.45.x） | 做 adapter——原生二进制、跨平台编译成本高；双许可对 vendored 友好但 Rust 栈与项目语言栈不同，走外部进程契约更现实 |
| sharp | lovell | Apache-2.0 | Node.js 高性能图像处理（libvips 绑定）：缩放/格式转换/合成，SVG 经 librsvg 输入 | 活跃维护（0.34.x，@img/sharp 平台包） | 做 adapter——原生依赖 libvips，非纯 JS、平台绑定；E0 契约适配（CLI/服务） |
| pypdf | py-pdf 组织（社区，前身 PyPDF2） | BSD-3-Clause | 纯 Python PDF 读写：合并/拆分/旋转/加密/水印/表单/元数据 | 活跃维护（5.x 持续发版） | **可直接吸收源码**——BSD-3 宽松、纯 Python、无原生依赖，可 vendored；是 PDF 验证器/契约实现的最佳样板 |
| reportlab | ReportLab Ltd（Andy Robinson 等） | BSD 风格（ReportLab 商业友好许可） | Python PDF 生成：排版/表格/图形/RML，底层 PDF 画布 | 活跃维护（4.x） | 做 adapter / 仅参考——纯 Python 核心可 vendored 但体量大；验证器仅标准库下倾向 adapter 而非吸收 |
| Pillow | python-pillow（Jeffrey A. Clark 等） | HPND（MIT-CMU 风格） | Python 图像读写/处理：PNG/JPEG/WebP、ImageDraw/ImageFont 绘制、滤镜 | 活跃维护（11.x） | **可直接吸收源码**（许可宽松）——但含 C 扩展，vendored 需构建；纯标准库验证器用不到，图像操作走 adapter |
| OpenCV（cv2） | OpenCV 组织（Intel 起源） | Apache-2.0 | 计算机视觉/图像处理：滤波、几何变换、特征、轮廓、OCR 预处理 | 活跃维护（4.x/5.x） | 仅参考——C++ 核心 + Python 绑定，体量大，不适合 vendored；对设计验证器价值有限 |
| ImageMagick | ImageMagick Studio（John Cristy 创建） | ImageMagick License（SPDX: ImageMagick，Apache-2.0 衍生） | 命令行图像瑞士军刀：magick/convert，200+ 格式（含 SVG），合成/变换/元数据 | 活跃维护（7.x） | 做 adapter——CLI 契约、外部进程调用；不适合 vendored |
| GIMP 脚本（script-fu / python-fu） | GIMP 项目（GNOME 社区） | GPL-3.0-or-later | 位图编辑器脚本化：script-fu（Scheme）、python-fu（GIMP 2.x），GIMP 3 新插件 API | 活跃维护（GIMP 3 已发布） | 仅参考——平台绑定 + GPL 传染；CLI --batch 能力弱于专用库，对 DESIGN-LAB 无吸收价值 |

## 关键结论（对 DESIGN-LAB 的落地建议）

1. **可直接吸收源码（宽松许可 + 轻量纯实现）**：pypdf（BSD-3，纯 Python PDF 契约样板）、@figma/rest-api-spec（Apache-2.0，纯 OpenAPI 类型，直接生成 E0 契约验证器）。
2. **做 adapter（E0 契约，平台中立）**：figma-js/Figma REST（网络契约）、Blender bpy 与 Inkscape CLI（子进程契约）、ImageMagick/sharp/resvg/svgo/CairoSVG（格式操作契约，全部为外部进程或原生依赖，符合验证器仅标准库约束——验证器不依赖它们，操作器走 adapter）。
3. **仅参考**：uxp-toolkit/ExtendScript/aio-lib-photoshop-api/Figma 插件沙箱（Adobe/Figma 私有平台）、svglib（LGPL+reportlab 强依赖）、OpenCV（体量）、GIMP（GPL+平台绑定）。
4. **共同约束**：所有渲染/操作类库（CairoSVG、resvg、sharp、ImageMagick、Pillow 的 C 扩展）都带原生依赖，与 DESIGN-LAB 验证器仅标准库原则冲突——验证层必须自研纯标准库实现，渲染/操作层统一走 adapter 外部进程。
5. **resvg 许可证变更值得注意**：MPL-2.0 → MIT/Apache-2.0 双许可（v0.45.1 起），若未来选 Rust 渲染后端，vendored 门槛已降低。

## 来源（关键核实链接）

- uxp-toolkit：https://github.com/bubblydoo/uxp-toolkit
- aio-lib-photoshop-api：https://github.com/adobe/aio-lib-photoshop-api
- figma-js：https://github.com/jemgold/figma-js （npm 1.16.1-0，depscope health 47/100）
- @figma/rest-api-spec：https://github.com/figma/rest-api-spec
- Blender bpy：https://projects.blender.org/blender/blender （GPL，blenderkit 等 addon 均带 GPL 头）
- Inkscape CLI：https://gitlab.com/inkscape/inkscape （Debian COPYING 确认 GPL-2.0-or-later）
- CairoSVG：https://github.com/Kozea/CairoSVG
- svglib：https://github.com/claudep/svglib （fork 自 bitbucket deeplook/svglib；FreshPorts 标注纯 Python）
- svgo：https://github.com/svg/svgo （v4.0.0 发布确认）
- resvg：https://github.com/linebender/resvg （relicense 公告 https://linebender.org/blog/tmix-10/ ；v0.45.1 LICENSE-MIT）
- sharp：https://github.com/lovell/sharp
- pypdf：https://github.com/py-pdf/pypdf （5.x 持续发版）
- reportlab：https://www.reportlab.com / PyPI reportlab
- Pillow：https://github.com/python-pillow/Pillow （LICENSE 为 HPND 文本）
- OpenCV：https://github.com/opencv/opencv （Apache-2.0）
- ImageMagick：https://github.com/ImageMagick/ImageMagick （SPDX: ImageMagick）
- GIMP：https://gitlab.gnome.org/GNOME/gimp （GPL-3.0-or-later）
