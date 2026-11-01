# EAGLE_INTEGRATION（Eagle 设计资产管理接入方案，2026-08-19）

> Eagle（eagle.cool）＝本地设计资产管理器（商业软件）。接入作为 DESIGN-LAB 的设计资产库层。

## 一、接入通道（官网核实）

| 通道 | 说明 | 状态 |
|---|---|---|
| **Eagle Web API**（developer.eagle.cool/web-api） | 本地 HTTP API：http://localhost:41595；库操作（switch/history）+ 素材查询/导入 | 🔵 需 Eagle 安装 + 设置开启 API |
| **eagle-mcp-server**（npm，MIT，1.1.7） | MCP server：agent 管理本地媒体文件（图片/音频/视频） | 🔵 可安装（需 Eagle 运行） |
| **Eagle Plugin API** | 插件 SDK（扩展 Eagle 功能） | 📖 参考 |
| **comfyui-eagle-feeder** | ComfyUI 自定义节点：生成图像直接发到 Eagle | 📖 关联（ComfyUI 通道已接） |

## 二、与本项目对接

- **资产层**：Eagle 库 ↔ DESIGN-LAB 外置资料摄取（P0-005 SourceRecord/ExtractionJob/CandidateKnowledge）——Eagle 素材经 Web API 查询/导入摄取管线
- **操作层**：eagle-mcp-server 走 MCP 通道（与 PS/Illustrator MCP 体系一致）
- **生成闭环**：ComfyUI 生成 → eagle-feeder → Eagle 归档

## 三、本机状态与前置

- **Eagle 未安装**（无进程/端口 41595）——需你安装 eagle.cool（商业）并在设置开启 Web API
- 安装后可：验证 Web API（localhost:41595）+ 安装 eagle-mcp-server + 连接验证

## 四、已登记

- adapter-eagle-webapi（E0：asset.query/import/library.switch）
- adapter-eagle-mcp（E0：asset.query/import，MIT）


## 更新（2026-08-19）：本机确认

- Eagle 已安装（D:/Program Files/Eagle/Eagle.exe）并启动（5 进程）——此前漏查 D 盘，已修正
- **Web API 未开启**（localhost:41595 拒绝连接）：需在 Eagle GUI 设置中启用（设置 → 服务/Web API → 开启，默认端口 41595）
- 开启后即可验证 asset 查询/导入 + 安装 eagle-mcp-server
