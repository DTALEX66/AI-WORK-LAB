# Native task execution implementation plan

> 执行方式：当前单写者原地执行；用户已授权持续推进，不新开并行写者或更改 main。按测试驱动逐项验证，不把计划当完成。

**Goal:** 将已实测 AI/PS adapter 接入现有 service SQLite 的 operation/attempt 与原生资产发布。

**Architecture:** `NativeTasks(ProjectService).execute(project_id, host, job, idempotency_key, approved_root, authorization)` 为内部同步入口；固定 host enum。复用 job_store 的短事务和状态转换语义、asset_store 的带 fencing 发布。新增同库持久化宿主占用表，不使用超时自动释放或第二套任务账本。

**Tech stack:** Python 3.11+、SQLite、现有 COM adapter。外置输入路径通过项目解析器；新工程和证据只在 `.project-local`。不接触 E 盘、用户原工程、凭据或全局配置。

**Spec:** 本文设计与 `docs/decisions/R3-PHOTOSHOP-INSTALLED-ADAPTER-2026-09-08.md` 的接续要求；完整目标仍以 R3 和用户目标为准。

## 接口与不变量

- 输入 job 和输入文件 hash 一起绑定 operation 的 idempotency key；调用方授权记录单独保存，不替代 Human Jury/rights。
- 同一 service 下每个宿主一个不可自动过期的 guard，和 PENDING→RUNNING 在同一事务获得。多个项目不能同时写同一宿主。
- 原生回执、输入/输出 hash 校验后，以现有 publish_version 发布主 AI/PSD，再读回发布文件。receipt 与版本结果、RECEIPTED、guard 释放同事务完成。
- 已完成任务从数据库读回并重新校验产物，不再进入 COM。不同请求相同 key 拒绝。
- adapter 明确预检拒绝且无副作用时，记录 FAILED/RETRYABLE 并释放 guard；COM 超时/未知/发布失败保留占用及部分效果，禁止自动重试。
- 取消仍用 job_store；PENDING 取消不进入宿主，执行过程中不假称 Adobe 已停止。
- 此入口不含任意脚本、HTTP 接口、自动 rights 批准或复杂参考质量验收；这些是后续接线，不作为本次完成声明。

## Task 1: 持久化执行切片

Files: `src/design_lab/native_tasks.py`；`design-lab/tests/test_native_tasks.py`。

- [x] 写真实 SQLite/文件测试：executor 缺失 RED、同键重启复用、改请求冲突、并发宿主占用、超时占用不释放、明确预检拒绝可继续、坏回执不登记、发布失败不重跑。
- [x] 运行 `.venv/Scripts/python.exe -B -m unittest discover -s design-lab/tests -p test_native_tasks.py` 并观察失败。
- [x] 实现封闭入口、输入快照、事务 guard、现有 asset 发布与终态持久化；不修改旧任务 schema。
- [x] 同命令 GREEN；相关组 82 项 PASS。实际 COM 边界才允许 double，其余使用真实文件及数据库。

## Task 2: 真实宿主与交付验证

- [x] 用新项目和新 run 调用 NativeTasks 生成 PSD/AI；重建服务对象并相同 key 重试，证明只有一次宿主执行、同一原生资产版本。
- [x] 明确记录源码 SHA/hash、原生回执、项目发布路径/hash 和剩余取消/恢复/UI 限制，见 `docs/decisions/R3-NATIVE-TASK-EXECUTION-2026-09-08.md`。
- [x] 最终源码聚合树运行统一检查 `design-lab/scripts/verify_design_lab.py`，会话 9148：49/49 PASS；通过生成器刷新报告并 `--check`。
- [ ] 仅提交本轮已核验文件，push 开发分支，直接读回远端 SHA 与新 CI 状态；不合并 main 或 release。
