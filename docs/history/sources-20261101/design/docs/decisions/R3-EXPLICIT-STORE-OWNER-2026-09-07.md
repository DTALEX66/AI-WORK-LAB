# 已安装运行时的任务与资产所属项目

状态：IMPLEMENTED_LOCAL；本切片不表示任务 HTTP、worker 或设计生产闭环已完成。

基准：`d59a472cc32129dfe9f1df7a22766d3064a83600`。可安装 CLI/HTTP 已明确所属项目，但 job_store、state_store 与文件发布路径仍使用源码模块位置推算项目根，在真实安装场景不能借用该默认值。

## 变更

为 `job_store.connect`、`state_store.init_db`、`asset_store.publish_version`、`asset_store.recover_publications` 添加可选关键字 `project_root`，统一传入现有 `resolve_paths`。旧源码调用签名兼容；显式根使用既有 marker、运行根、链接和数据库旁路文件检查，不新增扫描或磁盘豁免。

## 证据

`test_runtime_explicit_project.py`：初始 3 FAIL（尚无显式根参数），接入后验证任务创建并重连读回、状态 schema 初始化、真实 SVG 字节发布并读回、无残留恢复、拒绝相邻项目数据库/产物路径；3 PASS。

一次夹具错误将资产类别传成扩展名 `svg`，现有类别合同要求 `vector`；未创建资产行导致后续外键失败。修正夹具后通过，没有改 schema 放宽类别。既有资产事务 18 PASS、Attempt 23 PASS。

文件是合成 SVG 存储 fixture，不是 Illustrator 操作证据；任务保持 PENDING，不伪造 worker 执行。恢复测试只证明已提交项目无需恢复，崩溃/隔离语义另由既有事务回归覆盖。

后继：服务调用端必须始终把自身 ProjectPaths.project_root 传给这些函数；仅新增可选参数不证明所有旧调用或宿主入口都已迁移。任务/事件/取消 API、真实导入与产物交付仍需接入。

## 安装后实测

独立 wheel SHA256：`833ae3f21b65c40bf363b7c6f9e3200b8cfa6579ece579ba6c537e094a34fe25`。以 `--no-deps` 安装到 `.project-local/task-runtime/explicit-owner-qualification/venv`，使用该环境 Python `-I -B` 执行同一测试文件，`DESIGN_LAB_TEST_INSTALLED=1` 禁用测试源码路径注入，3 项全部 PASS。任务 SQLite 和已发布 SVG 字节均真实产生于合成拥有项目内，不是内存数据库或安装布局替身。

安装 wheel、测试环境均为 ignored 本地材料，不上传为正式发行物；不代表图像分析等完整依赖资格。
