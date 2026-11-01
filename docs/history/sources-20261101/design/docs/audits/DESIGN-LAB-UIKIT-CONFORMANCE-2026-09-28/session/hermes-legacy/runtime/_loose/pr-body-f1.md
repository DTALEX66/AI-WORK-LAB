## 范围

**Batch F-1**：把 effective evidence 接入 Release Gate（P1-B 的另一半语义）+ reports 重绑 + 交接文档同步。3 个 commit，基线 `eea6701`。

| commit | 内容 |
|---|---|
| `3e765dc` | `verify_release_gate.py` 改用 **effective** 级别比较 `minimumRequiredEvidence`；新增 15 用例测试 |
| `c2a40bd` | reports 绑定输入重绑（脚本/测试是报告摘要的绑定输入） |
| `56e4f31` | 交接文档同步（#125/#127 合并 SHA、F-1 增量、重录纪律补"观测 SHA 须为祖先"这条） |

## 为什么需要它

P1-B 已把 recorded / effective 分离，但 Release Gate 仍用 **recorded** 比较 floor，于是 `creative-toolchain` 的历史 E3 记录（绑定 `lastVerifiedTree=70dfc35c`）仍能满足其 E3 floor —— 门禁说谎。

现在：`capability_floor_findings()` 通过 importlib 载入 `effective_evidence.py`，比较 `meets_floor(effective, minimum)`；当前 SHA 取自 `git rev-parse HEAD`（不可解析时降级为空串，使所有 SHA 绑定记录被降级 = fail-closed）。

```
EVIDENCE-BELOW-MINIMUM <id> actual=<effective> minimum=<floor> recorded=<rec> effective=<eff>
EVIDENCE-REQUALIFICATION-REQUIRED <id> recorded=<rec> effective=<eff>   ← 降级时的可区分 finding
```

「需要重新取得运行时证据」不再与「从未达到 floor」混为一谈；模块不可用时**阻塞**（`EFFECTIVE-EVIDENCE-MODULE-UNAVAILABLE`）而非静默回退到 recorded-only。

## 实测效果（本树）

```
before: RELEASE_GATE=BLOCKED findings=7     ← creative-toolchain 通过了它自己的 floor
after:  RELEASE_GATE=BLOCKED findings=9
  new: EVIDENCE-BELOW-MINIMUM creative-toolchain actual=E1 minimum=E3 recorded=E3 effective=E1
  new: EVIDENCE-REQUALIFICATION-REQUIRED creative-toolchain recorded=E3 effective=E1
```

其余 4 项 BELOW-MINIMUM（design-intelligence、production-handoff、professional-visual-domains、visual-quality）**实质未变**（仅行格式多了 recorded/effective），`EVIDENCE-CARDS-PENDING`、`HUMAN-ACCEPTANCE-PENDING (DL-REL-001)` 均照旧。

## 验证证据（主线独立重跑，未采信子代理自报）

```
design-lab/tests/test_release_gate_effective.py + test_release_gate.py   Ran 20 tests  OK
  （含回归守卫 test_recorded_only_comparison_would_have_missed_it —— 证明旧比较确实会漏掉该 capability）
design-lab/tests/test_effective_evidence.py（P1-B，未改动）              Ran 27 tests  OK
verify_design_lab.py                                                     VERIFY_DESIGN_LAB=OK total=49 failed=0
scripts/verify_authority_gates.py --zero-spill                           AUTHORITY_GATES=PASS gates=7 failed=none
verify_release_gate.py                                                   RELEASE_GATE=BLOCKED findings=9（与自报逐行一致）
```

## 诚实标注

- 既有测试 `test_release_gate.py` 的两个调用点因新签名更新，期望值**被强化**（现在额外断言 `recorded=`/`effective=` 与 `actual=E1 minimum=E3`），非削弱；`test_effective_evidence.py`（27 用例）未被触碰。
- 跑门禁链会把 `reports/current/LANGUAGE-BOUNDARY-SCAN.json` 的 `generated_at` 改写，已 `git checkout --` 还原，本 PR 不含该时间戳噪音。
- `generate_current_reports.py --check` 在本分支结尾返回 **`STALE`**（不是 DRIFT）：内容逐字节稳定，但记录的观测 SHA 已被后续 commit 越过；该检查文本自带「rebind required - not a product-pass claim」，且提交重绑本身又会再推进一次 HEAD，属自指特性。此检查不在 CI 门禁内。

## 未做（保持 OPEN）

P1-A 版本沿革/取代血缘（需先 ADR）、Batch F 其余（release-preflight 强化、Host E3 预置脚手架）、真实 Host E3 / 人工 E4（owner 排除）。
