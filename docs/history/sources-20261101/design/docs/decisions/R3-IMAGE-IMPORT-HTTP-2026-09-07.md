# 真实图片导入、不可变资产与任务回执

范围：R3-09 / R4-009 的真实导入切片；不是参考拆解、设计生成、Adobe 或 M1 完成。

## 合同

- `POST /api/projects/<id>/assets` 接受且仅接受 `content_base64` 与 `idempotency_key`。不提供任意本地文件路径。编码体积上限 45,000,000 字符、解码图片上限 32 MiB、像素上限 25,000,000；只接单帧 PNG/JPEG。
- 使用 Pillow 实际校验并解码，保留原编码字节；不重压缩、不转格式、不删除原用户文件。无 Pillow 时返回依赖不可用，而非模拟图片信息。
- 使用已有 job_store.begin_attempt/transition 绑定请求 hash 与导入键、已有 asset_store 发布和 fencing 锁；没有第二套任务真值表。
- 输入副本位于 `.project-local/task-runtime/image-imports/<attempt>/input`，最终文件位于 `.project-local/projects/<project-id>/assets/versions/<publication>/reference.png|jpg`。存储与数据库全部传入显式拥有项目根。
- 原子发布后重新读取实际输出、校验 hash/尺寸，才转 RECEIPTED。相同键/相同图片可读回同一结果；相同键/不同图片 409；运行中断或异常保持未知、要求对账，不自动再次执行。
- `GET /api/projects/<id>/assets` 返回经当前文件核验的资产；`.../<asset-id>/content` 返回原编码字节的 base64。每次读回重新验证所属项目、路径、大小和 hash；篡改不能复用旧成功回执。
- rights 固定 `NOT_REVIEWED`，导入不签署素材来源、商业许可、Quality 或 Release gate。

## 本地验证

源代码 CLI 子进程 + 真实 loopback HTTP：原 8 项 HTTP 测试、5 项图片测试共 13 PASS。图片测试覆盖 PNG 导入与重启、幂等重放、改请求拒绝、不合法图像、跨项目读取拒绝、发布后字节损坏拒绝、JPEG 原编码无损读回。

RED 初始三项新接口测试返回 404；实现后通过。首次全组测试另遇 Windows TemporaryDirectory 清理 WinError 32/5：该目录同时是已终止服务的 CWD，但未定位具体锁持有者，不宣称已证明锁根因。改为启动于持久的项目内测试父目录，数据仍在独立夹具目录；后续 11/13 项测试均清理成功。未提升权限、未杀共享进程、未修改 ACL；旧失败空目录没有手工删除。

## 未完成

这是同步本地图片导入，不是异步设计 worker。输入副本暂保留供对账，没有声称缓存清理完成。未知结果自动修复、任务/事件查询与取消接口、导出封装、正式工作台、参考拆解和真实 AI/PSD 复刻仍需继续。25M 像素限制不是解码进程隔离或性能资格，当前本机可信用户入口不能当公开网络服务部署。

## 安装与故障验收追加

- 从 uv.lock 导出非开发依赖到项目内 ignored requirements，独立环境实际安装 15 项锁定依赖与本项目 wheel，不更新锁文件或全局 Python。
- wheel SHA256 `760e791b3590a0e76d99909da9a7a9178d4b829fb1783c53d8600279c900d87f`；实际 39 个成员全部仅 package/dist-info，无运行缓存目录。
- 安装环境 `.project-local/task-runtime/import-qualification/venv` 的 Python `-I -B -m design_lab` 从非源码目录运行，13 项 HTTP 验收全部 PASS。Pillow 12.3.0 实际解码与原始字节读回；安装了全依赖不等于所有算法/模型已验证。
- `test_image_import_recovery.py` 1 PASS：在真实文件 rename 后注入 OSError，数据库无 ACTIVE 版本，Operation/Attempt 均 OUTCOME_UNKNOWN；相同请求不创建第二个 attempt；已有恢复 API 把实际文件移入 QUARANTINED，字节完整。这是本机故障注入，不是宿主取消或独立人工验收。
