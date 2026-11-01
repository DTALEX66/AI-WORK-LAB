# 可安装服务的实施前设计

状态：DESIGN_ONLY。属于 R3-09 / R4.1 DL-R4-009，不能作为服务已安装、API 已运行或 M1 完成证据。

## 当前阻断与复用点

现有 `src/design_lab` 已有 asset_store、job_store、operation_coordinator、profile_resolver、doctor；继续复用它们，不另建平行项目/任务账本。`asset_store.create_project(conn, project_id, display_name)` 和现有 project 表可承担项目持久化。

但是 `state_store.DDL`、`job_store._SCHEMA_ROOT`、`asset_store._SCHEMA` 通过源码 `parents[3]` 寻找 `design-lab/schemas/state`；`runtime.paths.PROJECT_ROOT` 也绑定源码位置。直接将 pyproject 的 package=false 改成 true 不会成为真正可安装服务。必须先验证 wheel 中资源与显式项目根，不能用测试 sys.path 掩盖。

## 设计决策

1. SQL 仍以现有 `design-lab/schemas/state/*.sql` 为唯一编辑源；构建时纳入包资源，安装后用 importlib.resources 读取。构建派生资源不得成为第二编辑源；逐文件 hash 验证源码与 wheel 一致。
2. 安装位置与作品/运行项目根分离。CLI 显式 `--project`，没有项目时只读报错，不自动写 site-packages、用户目录或当前非 Git 文件夹。运行根沿用项目路径合同。
3. DB 连接仍由现有迁移函数初始化，保留备份、事务与单写语义；HTTP 每次请求使用独立连接，不跨线程复用 SQLite connection。
4. API 第一段为 health、项目创建/列表/详情与环境诊断；其后才接导入、operation/attempt、事件、取消和导出。未连接的宿主/provider 明确不可用，不能返回模拟成功。
5. 服务仅绑定 127.0.0.1；请求 Host 必须匹配实际监听地址，拒绝未知 Origin/跨站写入、过大请求、路径穿越和未知字段。不提供任意 shell、任意脚本或任意文件读取 API。
6. 用户工程导入遵循显式文件选择/授权范围、内容 hash 和受控副本；仅凭用户给出一个路径不允许扫描整块盘。网络上传、付费、模型下载不由本地 API 隐式触发。
7. 服务事件和原生回执绑定同一 operation/attempt。取消只请求取消，真实 adapter 确认和对账后才能终态；重启不能抹掉未知结果。
8. M1 最终仍需非仓库 CWD 启动、项目/任务重启持久、真实工作台交互、AI/PSD 两次局部修改与重开读回；健康端点和项目列表只是前置部分，不抵扣这些要求。

## 实施分段与验收

- 包资源/项目根：在项目 ignored 独立环境安装生成的 wheel，从项目内的非仓库子目录启动，验证 SQL 资源和既有迁移，不改全局 Python。
- 项目 API：真实 loopback HTTP 请求创建项目→GET 读回→停止自己启动的服务→重启→项目仍在；非法 Host/Origin/超限体积拒绝，失败不产生项目行。
- 任务 API：既有 attempt 真实状态机驱动；异请求同幂等键拒绝，取消未知不伪装取消完成，重启对账。
- 宿主/工作台联通：替换 fixture 回执为真实 adapter 验证，显示不可用/运行/失败/取消中/可重试，不能仅看 HTTP 200。

先处理包资源/路径，避免把运行数据写到安装目录。当前完整 Python 测试仍在会话 14679 运行；在其终态之前仅做上述只读接口调查与设计，未改服务源码或安装依赖。
