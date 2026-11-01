# 本地 HTTP 项目接口实施记录

范围：R3-09 / DL-R4-009 中的项目元数据传输层。不是完整服务或宿主闭环验收。

沿用 [实施前设计](R3-INSTALLABLE-SERVICE-DESIGN-2026-09-07.md)，复用 ProjectService、asset_store 与现有 SQL，不创建第二套任务或资产账本。

## 接口合同

- `design-lab --project <explicit-owning-root> serve --port 0`：仅绑定 `127.0.0.1`，端口 0 自动分配；标准输出只给地址与 LISTENING 状态。
- 启动器通过 stdin 管道提供本次运行的 64 位十六进制随机访问密钥（32 随机字节）；不使用命令行参数、磁盘凭据、日志或远端账户。密钥不得出现在交接或证据输出中。
- 所有实现的 API 请求带 `Authorization: Bearer <ephemeral-value>`，严格校验实际 Host 和同源 Origin；拒绝跨站 Fetch Metadata、重复关键头、chunked 请求、超限请求体与未知字段。
- `GET /api/health`：状态及明确的 `project-metadata` 能力范围。
- `GET /api/environment`：项目解析路径，不扫描外置库。
- `GET /api/projects`、`GET /api/projects/<id>`：只读列表与详情，无数据时不创建库。
- `POST /api/projects`：仅接受 JSON `{ "name": "..." }`，成功后返回 201 和真实持久记录。
- 不提供 shell、用户任意路径读取、上传、下载、宿主执行、虚构任务进度或 CORS 放行。

## 验证方式

`design-lab/tests/test_service_http.py` 启动真实独立 CLI 子进程，通过 loopback HTTP 请求验证创建、查询、停止自有进程、重启读回；数据库位于本项目 ignored 合成工程内。测试清理只处理自有子进程与 TemporaryDirectory。

初始 6 项 RED：尚无 serve 入口，进程退出且无 readiness。实现后 6 PASS；追加头歧义与非法 Unicode 测试，发现孤立 surrogate 导致 400 但创建了数据库，补充 service 写入前校验。

本层目前采用单线程 HTTPServer、3 秒 socket 超时、每响应关闭连接；只用于本地元数据切片，不能声称足以处理长时间模型生成或并发生产负载。启动器密钥交接与正式工作台衔接仍需验收。进程终止测试证明已提交元数据的重启持久性，不证明执行中模型任务的取消或优雅恢复。

未验收：任务/事件/导入/取消/导出 API、UI、AI/PSD 两次局部修改、完整依赖安装与 exact-SHA CI。权威账本不得因此提升整项为完成。

## 本次终态

- 源码进程：CLI 4 PASS、HTTP 8 PASS；资产事务定向回归 18 PASS。
- 新建独立环境、以 `--no-deps` 安装 wheel 后，使用安装环境 Python `-I -B -m design_lab` 运行同一组真实 HTTP 子进程验收：8 PASS，包含停止并重启后的项目详情读回。
- wheel SHA256：`43a7026829183087f2fb66248b678845a5e67280e69a84fe55b9f2c10fd725f5`，位置 `.project-local/task-artifacts/http-qualification/dist/design_lab-0.1.0a0-py3-none-any.whl`。
- 安装解释器：`.project-local/task-runtime/http-qualification/venv/Scripts/python.exe`；测试通过专用 `DESIGN_LAB_QUALIFICATION_PYTHON` 选择安装入口，未向子进程添加源码 sys.path。
- 该轮无宿主或模型调用、无全依赖资格证明。构建器提示缓存处于源码根；实际逐项检查 wheel 的 38 个成员全部仅在 `design_lab/` 与 dist-info 下，无 `.project-local` 或 `.hermes`，路径审计 PASS。
