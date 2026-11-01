## 范围

P1-B（recorded vs effective 证据分离）+ 交接文档定稿 + reports 重绑。5 个 commit，基线 `a3005be`。

| commit | 内容 |
|---|---|
| `7444792` | 交接文档定稿：§6 改为"已交付"（PR #126 合并 SHA、合并前 CI 9/9、exact-SHA 回读）；新增 §8 记录上传过程中查出的两个真缺陷 |
| `1810e51` | **P1-B**：新增 `effective_evidence.py`；`verify_capability_evidence_v4.py` 输出 effective 信息行 + 硬检查；`verify_release_evidence.py` 拒绝 requalified capability 的 E2-E5 release claim；新增 27 用例测试 |
| `56deb50` | reports bound-input 重绑（`capability-evidence-index.json` 是报告摘要的绑定输入） |
| `ca4a7e7` | rebase 后重绑 git 观测（rebase 重写了被记录的观测 SHA） |
| `bcf2529` | language 扫描重录（1954 个受跟踪文件） |

## P1-B 的语义

**recorded 是历史观测，不得满足当前树的 floor**。`creative-toolchain` 记录 E3 且 `requiresRequalification=true`（历史证据绑定在 `lastVerifiedTree=70dfc35c`），此前阶梯上仍读作 E3。

现在：`requiresRequalification` 或 `subjectSha != 当前 SHA` → effective 降为 E1（结构性通过时）否则 E0；release gate 比较的是 **effective**，不是 recorded。

```
EFFECTIVE_EVIDENCE visual-quality recorded=E1 effective=E1 requiresRequalification=true
EFFECTIVE_EVIDENCE creative-toolchain recorded=E3 effective=E1 requiresRequalification=true
EFFECTIVE_EVIDENCE style-master-method recorded=E1 effective=E1 requiresRequalification=true
CAPABILITY_EVIDENCE_V4=PASS records=8
```

## 验证证据（本 PR 的验证由主线独立重跑，不采信子代理自报）

```
verify_capability_evidence_v4.py        PASS records=8（信息行逐字一致）
design-lab/tests/test_effective_evidence.py   Ran 27 tests  OK
verify_design_lab.py                    VERIFY_DESIGN_LAB=OK total=49 failed=0
  verify_product_manifest_v3.py         OK total=493 failed=0
  verify_runtime_contracts_v3.py        OK total=239 failed=0
  open_design_host_adapter              OK total=549 failed=0
verify_authority_gates.py --zero-spill  AUTHORITY_GATES=PASS gates=7 failed=none
generate_current_reports.py --check     CURRENT_REPORTS=PASS mode=check
test_contract_schema_integrity.py       Ran 8 tests  OK
verify_release_gate.py                  RELEASE_GATE=BLOCKED findings=8（全部为既有 P1 残差，无 requalification 新失败）
```

## 诚实标注

- **effective 级别是计算得出的**（`effective_evidence.py`），索引里给 `creative-toolchain` 加的 `effectiveEvidence/effectiveNote` 仅供人读，**没有任何 verifier 消费它**（已 grep 确认）。
- schema 放行（`capability-status.schema.json` 白名单 `effectiveEvidence/effectiveNote`）按 P1-B 规格执行；经查该 schema 治理的是 `capability-status.json`（其 `capabilityRecords` 仅存在于那份文档），故对本次索引字段是**前瞻性允许**、无当前消费者。
- `verify_release_gate.py` 的 8 项 findings（4 项 capability 实际 E1 < 最低 E2、evidence cards 0/12、人工验收待做、分支态 SHA 不匹配）**均为既有 P1 残差**，本 PR 未改变。
- 已知既有行为（非本次引入）：`reports/current/LANGUAGE-BOUNDARY-SCAN.json` 由 `verify_language_boundary.py` 每次链跑重写并盖 `generated_at`，因此跑完门禁链后该文件总会显示 modified。

## 未做（保持 OPEN）

P1-A 版本沿革/取代血缘（需先 ADR）、Batch F 其余、真实 Host E3 / 人工 E4（owner 排除）。
