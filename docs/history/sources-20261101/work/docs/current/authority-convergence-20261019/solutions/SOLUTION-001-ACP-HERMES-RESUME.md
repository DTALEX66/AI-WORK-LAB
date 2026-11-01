# SOLUTION-001 — 不声明没有实现的能力（Hermes `resume`）

**ID:** SOLUTION-001
**来源问题:** `WORK-LAB-MINIMAL-LOOP-001`
**实现卡:** `docs/current/authority-convergence-20261019/implementation/WORK-LAB-MINIMAL-LOOP-001-ACP-HERMES-RESUME.md`
**状态:** VERIFIED（适配器层真实读回）；AAOS 候选 NOT_SUBMITTED
**日期:** 2026-10-19

## 1. 症状（可复现）

在仓库根运行 `scripts/ci/verify_acp_adapter_honesty.py`（AG-06 能力诚实门）时失败：

```text
ACP_HONESTY_FAIL DECLARED_CAPABILITY_WITHOUT_IMPLEMENTATION hermes advertises execution
capability 'resume' but resume() produced no real effect (probe=NOT_IMPLEMENTED,
overridden=False); the declaration is a false success surface
```

症状不是崩溃或报错给最终用户，而是**能力面说谎**：任何按 `capabilities()["supports"]`
选择路径的调用方都会看到 `resume` 并据此认为可以恢复会话，实际调用返回 `NOT_IMPLEMENTED`。

## 2. 根因

- `services/execution-federation/hermes_adapter.py` 的 `_capabilities()` 在
  `is_launchable()` 为真时把 `acp.Capability.RESUME` 加入声明集合。
- 该适配器没有覆写 `resume()`，继承的是 `services/execution-federation/acp_adapter.py`
  的基类实现；基类在声明了 `RESUME` 时返回 `NOT_IMPLEMENTED`（未声明时返回 `NOT_SUPPORTED`）。
- 因此这是纯声明错误：声明与实现分属两个文件，任何一侧单独看都自洽，只有能力门把两者对上时才暴露。
- 历史同类修复：Codex 与 OpenHands 适配器已于 2026-10-01 采用同一处理（不声明，直到有真实原生恢复），
  见 `services/execution-federation/codex_adapter.py` 与 `openhands_adapter.py` 中 `RESUME` 旁的注释。

## 3. 适用软件与版本

| 项 | 值 |
| --- | --- |
| 软件 | WORK-LAB 仓内 `services/execution-federation` 的 `HermesAdapter` |
| 代码基线 | `0369d349d46b75c7048b884331bb40a0f42d4e34`（修复前 HEAD；修复在工作树，未提交） |
| 修复前文件 | 5,364 B，SHA-256 `5e5579911ebf079e3b2a3501bf609b4fd2d488116b5089ad900c727f7369b943` |
| 修复后文件 | 5,697 B，SHA-256 `1735299435b743cc138a97b13b68bfb1c203130ddd6f6ac1427514418d1c3fe4` |
| 依赖 | Python 3.11（`.project-local/toolchains/wl-py311`）；无网络、无凭据、无外部进程 |
| 与 Hermes CLI 版本的关系 | 无关：不声明能力不读取或改变 CLI 版本；`is_launchable()`、`probe()`、`new()` 等行为不变 |

## 4. 修复步骤

1. 打开 `services/execution-federation/hermes_adapter.py` 的 `_capabilities()`。
2. 删除 `if self.is_launchable():` 分支中的 `acp.Capability.RESUME,` 一行。
3. 在能力集合构造处写明原因（AG-06：`supports` 不得成为假成功面；只有真实原生 resume 才能加回）。
4. 不做其他改动：不新增 `resume()` 桩、不改变 `new/prompt/cancel/fork`、不动注册表、不动受保护文件。

净差异：1 个文件，5 行新增、1 行删除。

## 5. 验证证据（真实读回）

| # | 检查 | 结果 | 收据 |
| --- | --- | --- | --- |
| 1 | `scripts/ci/verify_acp_adapter_honesty.py` | exit 0；`ACP_HONESTY_PASS executors=5 operations=40 executable=0 native_verified=0` | `.project-local/artifacts/authority-convergence-20261019/minimal-loop/01-acp-honesty.out` |
| 2 | `tests/workflow-assistance/test_execution_federation.py` | 12 tests / `OK` | `.../minimal-loop/02-federation-tests.out` |
| 3 | `tests/workflow-assistance/nf22_registry_and_acp_honesty_gates.py` | 49 tests / `OK` | `.../minimal-loop/03-nf22-tests.out` |
| 4 | 适配器静态+运行时读回（伪造可启动二进制） | verdict `PASS`；`supports` 14 项不含 `resume`；`resumeStatus=NOT_SUPPORTED`；`resumeOk=false`；6 项检查全真；适配器 SHA-256 `173529…c3fe4` | `.../minimal-loop/04-readback.out` |

第 4 项读回脚本：`.project-local/runs/authority-convergence-20261019/minimal_loop_readback.py`。
它先加载 `acp_adapter.py` 再加载 `hermes_adapter.py`，在临时目录放一个 `hermes-bin` 使适配器真的
走 launchable 分支（否则测不到出问题的分支），并断言非执行平面（policy/evidence/trace/budget/
handoff/acceptance）与执行平面（launch/session/fork/cancel/stream）都仍然存在——修复只删一个承诺，
没有连带删掉真实能力。

**证据边界：** 以上是适配器层读回，不是 Hermes 原生进程的真实会话恢复，也不是 exact-SHA CI。
`executable=0 native_verified=0` 是 AG-06 矩阵的既有读数，说明本仓从未证明任何执行平面真实可执行；
本方案不改变这一点，也不把它写成已验证。

## 6. 成功判据

- 能力门从红转绿，且它检查的是“声明有实现”而非“文件名出现 RESUME”。
- 删除声明后，调用 `resume()` 的返回从 `NOT_IMPLEMENTED` 变为 `NOT_SUPPORTED`——
  两个词的区别正是“声称能做但没做”和“明确说不支持”。
- 其余能力集合逐项不变；12 + 49 项回归测试全绿。

## 7. 失效条件（何时应重新评估）

- Hermes 原生提供真实的会话恢复接口并由适配器覆写 `resume()` 时：应连同实现、测试与真实读回
  一起把 `acp.Capability.RESUME` 加回；只加声明属于回归。
- `acp_adapter.py` 的基类语义改变（例如未声明也返回 `NOT_IMPLEMENTED`）时：本方案的判据
  “未声明 → `NOT_SUPPORTED`” 需重新核对。
- 若有调用方依赖 `resume` 出现在 `supports` 中来选择路径，那些调用方本来就是错的；
  应以能力门的失败为准，不得为兼容而恢复假声明。

## 8. 回滚

恢复被删除的一行 `acp.Capability.RESUME,`（并移除说明注释）即可；无数据、配置、状态或迁移。
回滚后 `verify_acp_adapter_honesty.py` 会回到修复前实测的红色，这是预期的可伪证性。

## 9. 失败与未做

- 未实现真实的 Hermes 会话恢复，也未声称实现。
- 未写 AAOS 知识候选：没有已接通的 AAOS API，且候选提交不等于接收。
- 未提交/推送：工作树改动等待 owner 授权；因此本记录不能作为 exact-SHA CI 证据。
- 未做其他适配器审计：本轮只处理能力门实际点名的这一个。
