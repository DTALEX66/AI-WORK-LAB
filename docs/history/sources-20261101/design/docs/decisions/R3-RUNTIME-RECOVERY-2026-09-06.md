# R3-05 / R3-06 运行状态、资产发布与恢复约定

状态：本地实现，仓库测试中；宿主集成与发布分别验收。
基线：`c4dccd58331bc4561eb89265283d924b7630d113`。
来源：用户授权推进 Codex 适用任务，R3 审计包的 R3-05 / R3-06 条款。
本文说明本轮实现，不替换 AGENTS 中的当前任务包或历史账本。

## Operation / Attempt

`begin_attempt` 将 operation ID、job ID、scope/key 与规范化 SHA-256 绑定。
调用方应使用 `request_hash(request)` 对完整 JSON 请求生成确定性摘要；对象键
排序，数组顺序保留，拒绝 NaN。摘要相同但身份冲突仍拒绝，不静默重绑定。

Worker 必须先提交 `PENDING → RUNNING`，只有抢到该转换的 worker 可以派发。
所有写 API 使用 SQLite `BEGIN IMMEDIATE`，事务失败整体回滚；存在调用方未提交
事务时拒绝嵌套写入，不替调用方提交或回滚。

| 情况 | Attempt / Operation 结果 | 后续动作 |
|---|---|---|
| 派发前失败 | FAILED / RETRYABLE | 显式 retry_attempt |
| 派发后异常或超时 | FAILED、TIMED_OUT / OUTCOME_UNKNOWN | 先宿主读回 |
| worker 崩溃，已停止旧 worker | recover_interrupted 将 RUNNING 改 OUTCOME_UNKNOWN | 不重新派发 |
| 读回确认副作用未开始 | FAILED / RETRYABLE | 创建 attempt_no+1 |
| 确认输出和读回 | RECEIPTED / SUCCEEDED | 返回原结果 |
| 只证明工具幂等或文档回退 | RECONCILING / PAUSED_NEEDS_USER | 继续对账，不能冒充成功 |
| 运行中请求取消 | CANCEL_REQUESTED | 等适配器确认 |
| 适配器确认取消 | RECONCILING | 检查实际宿主结果 |
| 确认取消且未开始副作用 | CANCELLED | 保持终态 |
| 取消与成功回执竞态 | 经绑定验证的成功可以先落账 | 迟到取消确认不能覆盖成功 |

`retry_attempt(job_id, previous_attempt_id=...)` 使用前驱编号比较：重复调用返回
同一后继，不另建尝试；过时前驱拒绝。已派发尝试需要已持久化的
`effect_not_started` 对账结果才能重试。失败终态本身不能当作无副作用证明。

成功回执要求 operation/attempt ID 和非零 artifact/readback SHA-256；由可信
适配器验证器生成。本层检查绑定和格式，不执行 Adobe 读回，也不能验证调用方
提供的文字声明是否真实。服务层接入时须把该 API 保留在可信适配器边界，不能
把用户输入的 hash 直接视为运行证据。人审、rights、视觉质量仍各自验收。

旧终态不重写。终态 UPDATE、历史 DELETE 和事件 UPDATE/DELETE 由数据库触发器
拒绝；迟到对账使用追加事件和独立 resolution 更新逻辑操作状态。
旧库中一个 Operation 对应多个 Job 时，禁止直接派发，先解决归属冲突。
旧 CANCELLED 经无副作用读回后仍为 CANCELLED；旧成功与无副作用证据冲突时
保持待核对并拒绝自动重试。取消确认在重开数据库后可幂等重放。

## 资产版本与文件发布

`record_version` 是受信任元数据导入接口，独立 UUID 标识 artifact，path 为属性。
版本及其全部 artifact 在单一事务中提交。新 ACTIVE 版本必须包含有 hash 和
正字节数的 artifact。该接口不读取文件；真正写文件使用 `publish_version`。

发布流程：

1. 校验源文件摘要、输出文件名和项目内 store root。
2. 在 SQLite 内检查 `asset:<asset_id>` 租约，提交 PREPARED 恢复记录。
3. 复制到独立 staging 目录，flush/fsync 并验证摘要。
4. 再次获得数据库写锁，验证 holder、generation、expiry 及 staging 摘要。
5. 原子 rename 到 `versions/<publication_id>/<name>`；验证文件与租约后，同事务
   提交版本/artifact 及 COMMITTED journal。

每个版本独立保存原始字节。同名 poster.psd 不覆盖旧文件。已经以 FAILED 或仅
元数据方式登记的同 hash 内容不会被暗中提升为成功发布，需要显式核对来源。

租约获取和接管在数据库写事务内原子完成；接管或过期后重新获取增加 generation。
续租不能复活已过期 token。释放也必须携带 generation，防止旧 worker 释放新锁。
旧 HELD 且无 expires_at 的锁需要显式接管，不能被默认为可执行或静默夺取。
损坏或非有限数值的到期时间同样要求显式接管。文件名在写 journal 之前校验，
拒绝 Windows 设备名、控制字符和非法分隔符。

写入根目前明确限制在本仓库 `.project-local/` 的子目录，拒绝符号链接/junction
和越界路径。R3-02 的统一作品库/路径解析器尚未集成，仓外作品库不是本轮写入范围。

## 数据库迁移与回退

入口 `job_store.connect` / `asset_store.connect` 自动识别 v2 标记。
执行前停止本项目 worker 并关闭宿主派发入口。已有记录时，先用 SQLite backup
在同目录创建唯一 `.pre-attempt-v2-<id>.bak` / `.pre-assets-v2-<id>.bak`；不覆盖旧备份。
迁移 SQL 在一个事务内执行，错误回滚；重复 connect 不再迁移。

Attempt v2 复制旧行，保留旧终态/时间/备注；旧回执无新证据的操作为
OUTCOME_UNKNOWN，需要重新核实。Assets v2 是新增 publication journal，旧
asset/artifact ID 和 path 保持不变。本轮只操作合成测试 DB，没有迁移用户实际 DB。

回退需冻结写入，保留完整 v2 DB、文件版本目录和 journal，再将迁移前备份复制到
**新的恢复 DB 路径**供旧版本只读诊断。比对并保留迁移后新增尝试、事件和资产记录；
未对账前不要恢复旧 worker 派发。直接覆盖当前 DB 会丢掉迁移后的记录，禁止用作
自动回退。完整版本降级与安装恢复属于 R3-24，尚未宣称完成。

## 文件系统故障恢复

`recover_publications(store_root=...)` 仅在本项目写入者停止后调用。它在数据库
写锁下查 PREPARED journal，将已经 rename 的 final 或尚在 staging 的文件移动
到 journal 预登记的 quarantine，保留字节；不创建 ACTIVE 空版本。
恢复本身在 rename 后崩溃时，下次能从 quarantine 继续，状态为 QUARANTINED；
确无文件则为 MISSING。不会自动删除用户资产。

本轮测试覆盖真实子进程退出、SQLite rollback、rename 故障和并发连接。
突然断电、外部程序篡改/删除已提交文件、真实 PSD/AI 宿主可编辑性仍需独立验收。
