## 范围

**Batch F-4：Host E3 预置脚手架**（可校验证据契约 + 探针 + **绝不伪造 E3**）。3 新 + 1 改。

## 为什么只做"脚手架"

审计明确：**真实 Adobe E3 不属本阶段默认完成条件**；没有 owner 授权与真实 Host 时，只能准备 **contract / test / evidence harness**，**不得制造 E3**。今天的实证缺口：
- `design-lab/schemas/` 下 **E3/host 证据契约 0 命中**（grep 证实）
- 现有 Photoshop/Illustrator 验证器只做 UXP 包的**静态结构**校验（`manifestVersion==5`、禁 `https://*` 通配权限、必备 UXP token）→ **没有任何机器可校验的 E3 证据形式**

## 交付内容

**1. 扩展 `design-lab/schemas/evidence-record.schema.json`（纯追加 +33/-2）**
复用既有通用契约 `EvidenceRecord`（E0–E5），新增可选 `host` 块（内层 `additionalProperties:false`，8 个必填子字段，`adapterSha256`/`artifacts[].sha256` 均 `^[0-9a-f]{64}$`，`readback`/`artifacts` `minItems:1`），并在根级表达 **`if level==E3 then required host`** —— **没有宿主来源的 E3 在契约层就不合法**；既有非 E3 记录不受影响。

**2. 新增 `design-lab/scripts/verify_host_e3_evidence.py`**（stdlib only，不联网，不写盘）
- 输出契约：`HOST_E3=<NO_RECORD|VALID|INVALID> records=N findings=[...]`
- 校验：契约（仓库 `jsonschema` 4.26，缺失时用等价内置子集校验器）+ `level==E3` + `approver` 非空 + `boundTreeSha` 等于 HEAD 或**真实祖先**（`git merge-base --is-ancestor`）+ `host.artifacts[i].sha256` 与**本地文件实际哈希**一致
- **无记录 → `NO_RECORD`（exit 0）**，并显式打印「当前没有 host E3 证据，能力等级不得因此提升」；`INVALID` → exit 1
- **不暴露任何 promote/write 助手**（已核验），绝不生成或推断 E3

**3. 新增 `design-lab/scripts/host_e3_probe.py`**（只读探测）
`HOST_E3_PROBE=<HOST_PRESENT|HOST_ABSENT> details=endpoint=…;adapter_packages=…;host_launched=false;network_used=false`；`HOST_PRESENT` **仅**由显式授权的桥接入口 `DL_HOST_E3_ENDPOINT` 触发 —— 适配器包存在或应用已安装**都不算**宿主运行面；**不启动任何宿主软件/GUI**。

**4. 新增 `design-lab/tests/test_host_e3_harness.py`（20 个用例）**，覆盖：伪造 E3（无 `host`）→ INVALID（两种校验引擎各一遍，含"没有 jsonschema 也不得开口子"）、artifact 哈希不符/文件缺失 → INVALID、`boundTreeSha` 无关 → INVALID、`approver` 空 → INVALID、非 E3 不计入、无记录 → **NO_RECORD（绝不 VALID/E3，"沉默不得变成等级"守卫）**、验证器无 promotion helper 且不向证据仓写入、探针不启动任何东西。

## 验证证据（主线独立重跑）

```
test_host_e3_harness.py                                   Ran 20 tests  OK
verify_host_e3_evidence.py                                HOST_E3=NO_RECORD records=0   + 「能力等级不得因此提升」
verify_host_e3_evidence.py --record <伪造 E3 负控>          HOST_E3=INVALID（schema: 'host' is a required property
                                                            + 没有宿主来源的 'E3' 是伪造的，不予通过）  exit 1
host_e3_probe.py                                          HOST_E3_PROBE=HOST_ABSENT
                                                            details=endpoint=unset;adapter_packages=…:present;host_launched=false;network_used=false
grep subprocess                                           subprocess 仅用于 `git -C … merge-base --is-ancestor`
verify_design_lab.py                                      VERIFY_DESIGN_LAB=OK total=49 failed=0
verify_authority_gates.py --zero-spill                    AUTHORITY_GATES=PASS gates=7 failed=none
```

## 诚实标注

1. **本 PR 不声明存在任何 E3 证据**，也不改变任何能力等级（`capability-evidence-index.json` 未改）。它做的是相反的事：**让伪造的 E3 无法通过**（已用负控证明）。
2. **探针在本机为 `HOST_ABSENT`**：适配器包存在，但没有显式授权的宿主桥接入口 —— 这是事实陈述，不是失败。
3. 该验证器**未并入** `verify_design_lab.py` 的 49 项聚合（total 保持 49）。它本身在无记录时 exit 0，理论上可安全并入（可让"提交一个伪造 E3 记录"直接让门禁变红）；并入会改变聚合计数（49→50）并可能触及计数契约，故列为**显式后续项**，不在本批夹带。
