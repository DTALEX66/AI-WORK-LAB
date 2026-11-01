# WORK-LAB 实时并行智能体调用 — 能力交接（HANDOFF）

日期：2026-09-20 · 分支：`u17/global-agent-policy-20260918` @ `bc3fe85`（本地 = origin，工作区 clean）
本交接仅覆盖「实时并行智能体调用」能力闭环（P1/P2/P3）；P0–§33 审计收敛见前序交接。

## 0. 一句话
在既有 Execution Federation 上叠加「把同一 ACP 操作并发 fan-out 到多个执行器 +
实时事件流 + 证据可查」的**被动编排层**——复用既有 `ExecResult` / receipts，
**不造第二套 engine / runtime / ledger**（§22 / §40 铁律）。

## 1. 交付物（4 commit，全部已推 origin）
| 层 | SHA | 内容 |
|---|---|---|
| P1 并发编排 | `69e1025` | `services/execution-federation/parallel_dispatch.py`：`ParallelDispatcher.fanout()` 并发派发 + per-route 失败/超时隔离 + fail_fast + 幂等去重 + 4 值聚合（OK/PARTIAL/DEGRADED/FAILED）回进**既有 `ExecResult`** |
| P2 契约 | `2d92c6d` | `packages/contracts/schemas/workflow/execution-parallel-dispatch.schema.json`（draft-2020-12），catalog 35→**36**，全动态（§4.1） |
| P3c 证据 | `c367e22` | `services/receipts/parallel_dispatch_evidence.py`：`ParallelDispatchEvidence.from_fanout()` 映射进**既有 receipts** 证据面（被动，无新 ledger） |
| P3f 流式 | `bc3fe85` | `parallel_dispatch.py` 增量：`fanout_stream()` 生成器 + `parallel_dispatch_stream()` 便捷函数（`__all__` 已登记）；schema +`events_stream`/`streamed` |

## 2. 用法（接手即可用）
```python
from parallel_dispatch import ParallelDispatcher, parallel_dispatch_stream

dispatcher = ParallelDispatcher(federation, max_workers=4, default_timeout=30)
res = dispatcher.fanout("new", ["hermes", "codex", "dsh"],
                        {"project_id": "X", "out_dir": "..."},
                        per_executor_timeout=30, fail_fast=False, adapter_kind="new")
# res.status ∈ {OK, PARTIAL, DEGRADED, FAILED}; res.executor == "*"
# res.payload = {per_executor, succeeded, failed, timed_out, unknown, events}

# 实时流（SSE / 监控）：逐事件 yield {executor, phase, ts, ok, status}
for ev in parallel_dispatch_stream(federation, "new", ["hermes", "codex"],
                                   {"project_id": "X"}):
    print(ev)   # STARTED → DONE/FAILED/TIMEOUT，真实实时（非 batch 后一次性）

# 证据：把一次 fanout 结果变成可审计的 receipts 证据行
from parallel_dispatch_evidence import ParallelDispatchEvidence
evidence = ParallelDispatchEvidence.from_fanout(res)
```
确定性测试全用 stub-adapter fake federation（不 spawn 真进程、不读 credentials）。

## 3. 关键语义（别改错）
- **被动**：dispatcher 只并发调用既有 adapter 的 `new()`/`prompt()`，**不 launch / 不读
  credentials / 不 apply policy**；`ThreadPoolExecutor` 只是并发形状，adapter 仍是 launch 决策源。
- **per-route 隔离**：一路 `FAILED`/`TIMEOUT`/`UNKNOWN_EXECUTOR` 绝不影响其它路；整批不崩。
- **DEGRADED ≠ FAILED**：全路 `NOT_LAUNCHABLE`/`NOT_SUPPORTED`（无硬失败）= DEGRADED，
  **不得**标 FAILED（P3c 证据 + nf 负控守住这条）。
- **fail_fast**：首路硬失败后，未启动路不发 STARTED、不发终态（被 drop）。
- **stream/batch 一致性 by construction**：`fanout_stream` 与 `fanout` 共享同一 `_RunState`
  的 `_run_routes` collector——yield 的事件 == batch `payload['events']`。
- **既有签名零改动**：`fanout()`/`dispatch_events()`/`parallel_dispatch_of()` 签名与返回
  契约未动（P3f 纯 additive，sub_C 的 receipts adapter 正依赖该稳定面）。

## 4. 可核验证据（分级）
- 本地全量 governance batch（gate `MODULE_PYTHONPATH`）：**160 modules / 1611 tests OK
  (skipped=8)，exit 0**；新模块 P1/P2/P3 共 7 个测试文件全部在批内绿。
- authority `AUTHORITY_REFERENCE_PASS`；CURRENT_STATE `FRESHNESS_PASS`（`source_digest=d8aca018…`，
  contracts=36）。
- CI 双 gate 全绿：
  - `2d92c6d`（P1+P2）：`work-lab-gate` `35467387812` success + `wlr-060` `35467387827` success
  - `bc3fe85`（P3）：`work-lab-gate` `35468657962` success + `wlr-060` `35468657960` success

## 5. 边界（不要越线）
- `merge_main = false`：exact-SHA + 双 gate 已就绪，**合并 main 由用户决定**。
- §40 DSH 保护、E/F 盘禁访、§22 无第二 engine 全程未触碰。
- register 里 A03/A04/U01/U17/U17a = **IMPLEMENTED（非 DONE）**（生命周期未 MERGED/READBACK/
  ACCEPTED）；U02 = PARTIAL。

## 6. 工具链（本机）
- venv：`D:/All projects/WORK-LAB/.project-local/runs/venv/Scripts/python.exe`（PyYAML+jsonschema）
- terminal 一律走 wrapper：`python C:/Users/ALEX/AppData/Local/hermes/bin/hermes-project-data.py
  --project . run -- <单命令>`（禁 shell 链/重定向/绝对 D:/ CLI 参数）
- 多段 PYTHONPATH 测试用 gitignored scratch runner（`.project-local/task-runtime/run_*.py`），
  已含 `run_p1_tests.py` / `run_p3_sub_c_tests.py` / `run_p3_sub_f_tests.py`。
- 提交多行 message 走 `-F <gitignored msg 文件>`（wrapper 把多行 `-m` 误判为 shell 链）。

## 7. 下一步（按需并行批推进）
1. 产品 UI：把 `fanout_stream` 接进 observer 实时面板（并行过程可视化）→ U03–U08 类。
2. 合并 main：用户点头即发 merge 决策（保留 exact-SHA + 双 gate 证据 + tag/readback）。
3. 继续 U03–U19：拆独立工作流并发，CI 等待期并发下一批。

## 8. 回滚
分支内小提交可逐步 revert；整段回退 `git reset --hard 2d92c6d`（丢弃 P3）/ `reset --hard
b1aa40a`（丢弃 P1+P2+P3）。仅本分支，不动 main。
