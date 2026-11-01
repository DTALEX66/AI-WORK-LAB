# PEER-ORIGIN-OSS ENHANCEMENT（同行/同类/同源/开源全景 + 操作能力增强，2026-08-19）

> 三组 web_search 核实（同行产品 16 / 同源相近 15 / 操作开源 6 类 30+）。重点：增强设计软件操作能力。

## 一、同源链（确认）

- 前身（OPEN-DESIGN 身份，WORK-LAB 20-design → 迁移 2026-08-07 → DL-MIG-000 git mv，已并入）→ DESIGN-LAB（MIT）
- 旧云端名 301 → DESIGN-LAB；归档 reports/history/ + docs/history/

## 二、同行/同类（对标）

| 类别 | 代表 | 借鉴 | 规避 |
|---|---|---|---|
| 商业 AI 设计 | v0/Galileo/Recraft/Lovable/Figma Make/Adobe Firefly/Relume | Recraft 品牌 style kit 锚定；Relume sitemap→wireframe 分层；Lovable 生成→运行→自修回路 | 闭源作 API/MCP 生态接口，不依赖 |
| 开源 UI 生成 | screenshot-to-code(MIT)/OpenUI(Apache-2.0)/v0.diy(MIT) | UI 生成引擎候选（多提供商路由） | tldraw make-real（AGPL 传染）不内嵌 |
| 相近项目 | nexu-io/open-design(89k★, 本宿主)/superdesign(6.8k★) | 宿主 plugin/skill schema 对齐 | — |

## 三、操作能力增强路线（重点）

| 层 | 方案 | 来源 | 状态 |
|---|---|---|---|
| **Photoshop 操作** | **Photoshop MCP**（alisaitteke/photoshop-mcp，MIT，102 工具 + Windows-first 变体）——MCP server 管理 PS 会话，替代不稳定 JSX | 组3 | 🔵 待接入（adapter 登记 + 验证） |
| Illustrator 操作 | illustrator-mcp-server（MIT，63 工具） | 组3 | 🔵 adapter 登记 |
| Figma 操作 | 官方 figma-developer-mcp（MIT）+ @figma/rest-api-spec | 组1/3 | 🔵 adapter 登记 |
| Inkscape 操作 | inkscape-mcps（MIT，CLI+DOM 双通道+安全边界） | 组3 | 🔵 adapter 登记 |
| Adobe 通用 | generator-app-remote-mcp-server-generic（Apache-2.0，官方） | 组3 | 🔵 adapter 登记 |
| 设计文件解析 | ag-psd/psd-tools（MIT，PSD 读写）→ 操作层参考（多文件库不 vendored） | 组3 | 🔵 参考 |
| 生成引擎 | screenshot-to-code/v0.diy/OpenUI → UI 生成后端候选（E0 登记） | 组1 | 🔵 候选 |
| 视觉回归 | pixelmatch（已吸收）+ Playwright（已登记） | 已做 | ✅ |
| token 管线 | Style Dictionary + token-transformer（MIT）+ DTCG（已做） | 已做 | ✅ |
| 封装模式 | HKUDS/CLI-Anything agent-harness（Apache-2.0，47.8k★）→ adapter 层封装参考 | 组3 | 📖 参考 |

## 四、规避/注意

- AGPL：tldraw make-real（不内嵌）
- 停维护：figma-js（上游 404）、psd.js、BackstopJS、Theo（被取代）
- 非官方：PyPI adobe-mcp（VoidChecksum 第三方）

## 五、执行顺序

1. adapter 登记：photoshop-mcp / illustrator-mcp / figma-mcp / inkscape-mcp / generator-mcp（操作层补全）
2. Photoshop MCP 接入验证（解决 PS 操作不稳定问题——最高优先）
3. 生成引擎候选登记（E0）
