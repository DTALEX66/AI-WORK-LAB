# DL 设计软件管理与操作开源全景（2026-08-18，web_search 三组核实）

> 范围：管理（资产/设计系统/token）与操作（自动化设计软件）设计类软件的开源项目全景。
> 方法：3 组并行 web_search（操作库 / 资产管理 / 软件本体与管线），逐项核实仓库/许可证/维护/适配判断。

## 一、可直接吸收源码（宽松许可 + 轻量/纯源码）

| 项目 | 许可证 | 用途 | 吸收方式 |
|---|---|---|---|
| pypdf（py-pdf） | BSD-3-Clause | 纯 Python PDF 读写/校验样板 | vendored knowledge/sources + registry + SBOM |
| pixelmatch（mapbox） | ISC | 轻量像素 diff 引擎（评审记分卡） | vendored（JS 零依赖） |
| chroma.js | MIT | 色彩引擎（配色/转换） | vendored（单文件） |
| @figma/rest-api-spec（官方） | Apache-2.0 | Figma REST OpenAPI 规范，生成 E0 契约 | 吸收规范文件为契约素材 |
| primer/prism、culori | Apache-2.0/MIT | 配色算法 | 参考吸收（评估体积） |

## 二、做 adapter（E0 契约登记，外部进程/网络/原生依赖）

| 项目 | 许可证 | 能力契约 |
|---|---|---|
| Inkscape CLI | GPL-2.0+ | svg.export（批量 SVG→PDF/PNG） |
| ImageMagick | 宽松（SPDX） | image.process（缩放/合成/转换） |
| sharp | Apache-2.0 | image.process（Node 侧，libvips） |
| resvg | MIT/Apache-2.0（2024 relicense） | svg.render（高质量 SVG→PNG） |
| svgo | MPL-2.0 | svg.optimize（v4.0 已发） |
| librsvg/rsvg-convert | LGPL-2.1+ | svg.export（多尺寸批量） |
| Blender bpy | GPL-2.0+ | three_d.operate（headless 建模/渲染） |
| figma-js | MIT | figma.read/export（REST 封装） |
| Penpot（自托管） | MPL-2.0 | penpot.export（REST：SVG/PDF/token） |
| Playwright toHaveScreenshot | Apache-2.0 | visual.regression（多尺寸基线对比） |
| BackstopJS / Lost Pixel / Argos | MIT | visual.regression（CI 视觉回归） |
| veraPDF | MPL/GPL/LGPL | pdf.preflight（PDF/X-1a/3、PDF/A 门禁） |
| Ghostscript | AGPL-3.0+ | pdf.render/compress |
| Style Dictionary | Apache-2.0 | token.build（token→CSS/Android 资源） |
| DTCG/W3C Design Tokens | W3C 免许可 | token.standard（对齐 Tokens Studio/Penpot） |

## 三、仅参考（私有平台/商业/GPL 传染/停更）

- Adobe 系：UXP toolkit、ExtendScript（停）、aio-lib-photoshop-api（云）、Figma Plugin API（沙箱）
- 商业/无开源许可：Chromatic、Percy、Applitools、Tokens Studio（仅借鉴工作流）、FontBase（闭源）
- GPL 传染/停更：GIMP、Krita、Pencil2D、Synfig、svglib、OpenCV（体量大）、ResourceSpace（BSD-4）、Razuna（AGPL 停更）、Piwigo
- 已停服：Gravit Designer（Corel 收购关闭）

## 四、空白区（需自研，无成熟开源）

- 品牌资产库管理（Reloops 新候选，许可未核实）
- 字体管理（开源替代均弱：Font Manager/FontMuse 不成熟）

## 五、执行建议（按优先级）

1. 吸收：pypdf / pixelmatch / chroma.js / @figma-spec（走 SOURCE_REGISTRY + SBOM 管线）
2. adapter 契约：注册 Inkscape/ImageMagick/sharp/resvg/svgo/Penpot/Playwright/veraPDF 等能力到 adapter-registry（E0）
3. token 对齐：现有 tokens.json 转 W3C DTCG 格式（低成本互通）
4. 条件引入：印刷需求出现时加 veraPDF（PDF/X 门禁）

## 六、来源（代表性链接）

pypdf、pixelmatch（mapbox）、chroma.js、style-dictionary、penpot/penpot、inkscape、resvg（linebender relicense）、svgo v4、veraPDF、Playwright snapshots、BackstopJS、lost-pixel、argos-ci、W3C designtokens.org、tokens-studio、ghostpdl
