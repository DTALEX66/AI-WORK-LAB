# AI/PS 持久化执行与原生资产登记交接

## 当前结果

新增 `src/design_lab/native_tasks.py`，将已实测的 Illustrator/Photoshop COM adapter 接到现有 service SQLite、operation/attempt、资产 fencing 和 `publish_version`。安装包实机已分别生成 AI/PSD，登记到 `.project-local/projects/`；重建服务对象并相同 idempotency key 重试，均返回同一 attempt 与资产版本，没有再次进入宿主。

基于 `60c8e2164cb8dad5e2ffd5e932a18c6872ac2566` + 本轮候选源码。该基线 CI `34152031556` 已读回 success；新提交 CI 另验。当前模块 SHA256 `c27f06b26eebfe28b0ea1eddc540d4a9d4143082c2a6b52fcfbf63bd45c43756`，实机使用安装目录模块，同 hash。**不是全部 R3/M1 完成，不是复杂参考 E3，不是人审接受或正式 release。**

## 内部调用合同

```python
NativeTasks(ProjectService(project_root)).execute(
    project_id, 'photoshop', job,
    idempotency_key='unique-key', approved_root=run_root,
    authorization={'actor': 'user', 'scope': 'project-native-test',
                   'receipt': 'recorded user approval for this scoped test'})
```

固定 host 仅 `illustrator` / `photoshop`；调用方声明的测试授权保存在本地请求，不等于验证了 rights，更不等于 Human Jury 签字。输出 `rights=NOT_REVIEWED`。尚未允许网页提交任意原生 job。

- 使用已有 `.project-local/task-runtime/service/state.db`，新增同库 `native_execution_v1` / `native_host_guard_v1` 辅助表，不建立第二套 operation 状态源。
- 完整 job、输入文件 hash、project/host 和调用方授权一起绑定幂等 key；同路径但输入变化也拒绝复用。
- guard 与 PENDING→RUNNING 在同一短事务内取得；每个 service 数据库中每种宿主只有一位持有者，跨该 service 的用户项目有效。
- guard 不过期；COM 超时、坏回执、发布失败后保留占用与部分文件。没有“60 秒到期就重试”的后门。明确 adapter 预检拒绝才记 FAILED/RETRYABLE 并释放；下一 attempt 必须显式由 job_store 创建。
- 原生回执核对完整 job hash、输入/输出 hash、文档数量；主 AI/PSD 通过已有带 fencing 的原子发布流程进入版本目录；发布文件重新 hash 后才事务提交 RECEIPTED/结果并释放 guard。
- 同键重放从数据库取结果，并重新验证主原生文件 hash；文件被改坏时不返回成功，也不重新运行宿主。
- 预览 PNG、附属 SVG 目前保留在原运行目录及原生回执中，尚未形成完整多文件生产交付包。ACTIVE 资产版本不代表人类接受版本。

## 真实安装包运行

Wheel `.project-local/task-artifacts/native-tasks-wheel/design_lab-0.1.0a0-py3-none-any.whl` SHA256 `bc8887ece65f0e22bf8ed07c037b7fe5d015d038530b1af5d2b70d70d1c21cce`；49 项，模块与源码逐字节一致，无缓存/`.project-local` 项。仅更新项目内资格 venv，无系统安装或 release。

| 宿主 | 项目 ID | 主原生文件 SHA256 | 重放证据 |
|---|---|---|---|
| Photoshop 26.7.0 | `d84752abf0b74715bc55518d52b7eb94` | `b66d721b6d8f539cde4f2a5da686968bf08300f5bec59092fe558c5838b9e134` | attempt 1、RUNNING 事件 1、剩余 guard 0 |
| Illustrator 29.5.1 | `a453fe888aaf4008a37a338c46bdeb07` | `6e887348185814f1a15b878a48d80ac61cd4351e812f8f206f7f4bdd6fd1701b` | attempt 1、RUNNING 事件 1、剩余 guard 0 |

PS attempt `att-68eacb45ca7e4516bb0811f6f04e2f82`，版本 `v-928cb30433ef41b3be8493edcad4ba9d`，UTC 18:41:25–18:41:31（约 6.47 秒）。结果位于 `.project-local/task-artifacts/native-task-live-20260908/run-a53d21f20aa44f019f16bb26b48ac5a1/result.json`。

AI attempt `att-328e9b2c870e449c881c0f9c538d84ed`，版本 `v-6d641133195244e89f84dd8a5ca805f7`，UTC 18:42:28–18:43:08（约 40.91 秒）。结果位于 `.project-local/task-artifacts/illustrator-lowering-20260908/run-9a138a99f3dc4b17b8cdeb3454d71566/native-task-readback.json`。

日期均为 2026-09-07 UTC（本地 09-08）。两宿主文档数量均 0→0。输入是受控合成 fixture，不计入 5–10 张复杂参考。项目资产位置由结果 JSON 的 `asset.path` 给出，可用 `.project-local/projects/<project_id>/assets/versions/` 定位；这些原生工程不上传 Git。

复现：先用 `prepare_photoshop_native.py` 或 `prepare_illustrator_lowered.py` 准备新 UUID job，再以已安装解释器执行 `python -I -B design-lab/tests/host_fixtures/qualify_native_tasks.py <project_root> <host> <job_json>`。该脚本只创建新的资格项目，不覆盖原运行文件。

## 测试与剩余限制

缺失 executor 时先观察 7 项 RED；实现后补到 12 项真实 SQLite/文件/线程测试，包含并发双执行、重启重放、输入变更、坏回执、发布 I/O 失败、取消前置、明确无副作用的显式下一 attempt 和主产物篡改。仅原生 COM 边界 double，不将测试生成的伪 PSD 头当实机证据。

82 项相关测试 PASS：native_tasks、runtime_attempt_safety、runtime_asset_safety、job_store、asset_store、Photoshop 与 Illustrator 组；模拟 CI 外层 PROJECT_LOCAL_ROOT 环境，4.487 秒。

统一检查会话 9148 终态退出 0，`VERIFY_DESIGN_LAB=OK total=49 failed=0`；报告生成/`--check` PASS。49 项统一检查不是全量 Python 单测；其历史 Comfy E3 字样不是本轮推理证据。新提交的 exact-SHA CI 必须重新查询。

尚未提供未知宿主的自动恢复/人工对账 API，guard 不可凭旧锁、进程观察超时或“已经过很久”自行清除；当前仍保守阻止后续宿主写。不能声称跨 checkout/不同 service 数据库的全机锁。未直接修改现有 SQL schema 原文；新增表是 v1 辅助合同。事务实现明确复用 job_store 内部 helpers，以便 guard 与既有状态原子更新，后续调整这些 helper 必须跑本组回归。

下一步优先：把原生任务/资产加入项目查询与工作台可见记录，再把已安装 RIR/参考拆解接到受控提交；补对象 patch、取消对账、完整交付包、多文档/重启恢复及复杂参考。Comfy/H3 15 秒小说分镜视频、人类 Jury、rights、production 仍未完成；知识迁移延后。不能只把按钮启用就声称闭环。
