# 工作台任务历史查询增量

基线 `40f34740e4b57db62d048c0655d5a45868c2066f`；本次新增真实本地 HTTP 查询，非前端或宿主完成声明。

## API 与范围

- `GET /api/projects/{id}/tasks`，可带 `?after={job-id}`。
- `GET /api/projects/{id}/tasks/{job-id}`。
- `GET /api/projects/{id}/tasks/{job-id}/events`，可带 `?after={event-number}`。

每页最多 100 条，有后续页时返回 next_cursor；最后一页为 null。
任务按 job_id 升序，事件按全局递增 event_no 升序。轮询新事件可保留已见的最大 event_no；
任务列表不是新建任务的时间游标，刷新列表应从第一页开始，新增随机 ID 可能排在旧游标前。

当前仅列出持久化 operation_intent 中明确绑定 `image-import:{project-id}` 的任务。
不靠路径或相似名称推定归属；其他未定义项目归属的宿主任务不混入此列表。
任务状态与最新 attempt 状态分别返回，不把 CANCEL_REQUESTED 当 CANCELLED，
不把历史 RECEIPTED 重新当作刚验证的文件或 rights 结论。
事件只含编号、attempt ID/序号、前后状态和时间；不外传 note、detail、request hash、幂等键或证据正文。

查询沿用 loopback、Host、Origin、Sec-Fetch-Site 和内存 Bearer 认证。
只读 SQLite URI + 读取事务，不运行 migration、不创建数据库。
新项目尚无任务时返回空页；有旧任务但未通过 attempt-v2 migration 时返回 503 TASK_SCHEMA_UNQUALIFIED。
非法/重复游标、未知 query、外项目任务返回错误，不执行任务或访问原生产物。

## 已执行验证

`test_service_http.py`：16 方法 PASS，真实 CLI 子进程、socket、SQLite 和图片导入；非伪 HTTP。
新任务列表测试在实现前因 404 而失败；实现后正向及负向通过。
覆盖：导入完成后退出/重启、项目隔离、空项目/缺失项目、不创建状态、非法 query。
另建 102 项真实 store 任务，首项经 51 次失败/显式重试到 attempt 52，再发出取消请求。
两页任务为 100+2；两页该任务事件共 105 条，编号无重复；最后状态 CANCEL_REQUESTED。
事件不包含合成私有 note；查询前后数据库 SHA-256 相同。
运行目录均在本仓 `.project-local/task-runtime/service-http-tests/` 的隔离子目录，夹具由测试自行清理。
统一门 `design-lab/scripts/verify_design_lab.py` 本轮运行终态 49 PASS、退出码 0。
报告生成与绑定输入完整性检查 PASS；上述检查不证明本轮 wheel 安装或真实设计宿主行为。

## 未完成与下一步

页面、实时事件流、异步调度、创建设计任务、取消/重试 HTTP 写接口、Adobe/Comfy worker 接入仍未完成。
下一步将已有项目/图片/任务读取接入工作台，再连接有资格与 receipts 的执行器；不展示虚构进度。
当前测试针对源码服务，未重新构建/安装本提交 wheel，不宣称安装资格刷新。
R3 仍为任务状态权威；知识迁移延后。代码可通过审查后的 revert/forward commit 回退，无数据库 migration。
