# OBJECT_MODEL_V42 — Project / Knowledge / Evidence / Artifact 四对象模型

- 版本：`4.2`｜任务：`V42-0204`｜状态：`ACTIVE`｜证据：E2
- 依赖：V42-0202（职责边界）、V42-0203（用户与模式）
- 机器可读：`design-lab/config/object-model.json`
  （schema：`design-lab/schemas/object-model.schema.json`）

## 目的

为项目工作流定义四个核心对象及其生命周期、版本、权利和引用合同，
保证**生命周期、版本、权利和引用均可验证**（E2：schema 校验 + 隔离执行证据）。

## 四对象总览

| 对象 | 职责 | 生命周期 | 版本 | 权利 | 引用 |
|---|---|---|---|---|---|
| **Project** | 一次商业设计任务的端到端状态 | intake→route→research→direction→system→execute→critique→preflight→handoff→approved | semver + iteration（可变） | owned（自有） | produces→Artifact；documents→Evidence；applies→Knowledge |
| **Knowledge** | 有来源的专业知识资产 | collected→reviewed→verified→runtime-eligible→retired | registry version + maturity（不可变） | review-required（必须审） | informs→Project；verified-by→Evidence |
| **Evidence** | 能力与结果的可验证证据 | recorded→verified→published→expired | exact SHA + timestamp（不可变） | owned（自有） | proves→Project；hashes→Artifact；validates→Knowledge |
| **Artifact** | 可编辑交付与生产产物 | draft→review→approved→delivered→archived | artifact version + sha256（不可变） | review-required（必须审） | belongs-to→Project；provenance→Evidence |

## 生命周期合同

1. 每个对象必须有明确的 **阶段（stages）** 与 **终态（terminalStates）**；
2. 终态是：`approved/superseded/cancelled`（Project）、`retired/quarantined`
   （Knowledge）、`expired/superseded`（Evidence）、`delivered/archived/superseded`（Artifact）；
3. 只有处于终态的对象才可被冻结/归档/引用为不可变证据。

## 版本合同

1. **不可变对象**（Knowledge/Evidence/Artifact）一旦记录不得改写，只能新增版本；
2. **可变对象**（Project）用 semver + iteration 演进，保留决策历史；
3. 版本标识必须能唯一定位到确切内容（Evidence=exact SHA；Artifact=sha256；
   Knowledge=registry version + maturity）。

## 权利合同

1. Knowledge 与 Artifact 默认 `review-required`（来源/许可必须人工审）；
2. Project 与 Evidence 为自有对象（`owned`）；
3. `licenseStatus` 枚举与 `provenance.schema.json` 的 `license_status` 对齐：
   `owned / allowed / reference-only / review-required / unknown`；
4. `review-required` 的对象在审结前不得进入 runtime prompt（不可破坏原则 #4）。

## 引用合同

1. 对象间引用必须声明 **target + relation**，不允许悬空引用；
2. 引用链可沿 `Project → Artifact → Evidence → Knowledge` 回查来源与权利；
3. 任何进入交付的 Artifact 必须有 `provenance`（Evidence）引用；
4. 引用必须可解析：目标对象存在且处于有效生命周期阶段。

## 与现有 schema 的关系

| 现有 schema | 对应对象 | 关系 |
|---|---|---|
| `design-project-state.schema.json` | Project | 阶段枚举对齐（intake..approved 子集） |
| `provenance.schema.json` | Artifact/Evidence | license_status 与 source_refs 对齐 |
| `source-registry.schema.json` | Knowledge | 来源、版本、成熟度字段对齐 |
| `capability-status.schema.json` | Evidence | 状态/证据等级枚举对齐 |
| `design-handoff.schema.json` | Artifact | 交付合同对齐 |

## 验证方式（E2）

```bash
python - <<'PY'
import json, jsonschema
base = "opendesign-assistance"
schema = json.load(open(f"{base}/schemas/object-model.schema.json", encoding="utf-8"))
inst = json.load(open(f"{base}/config/object-model.json", encoding="utf-8"))
jsonschema.validate(inst, schema)
print("OBJECT_MODEL_V42 schema validate OK")
PY
```

Gate：schema 校验通过、四对象齐全、生命周期/版本/权利/引用字段完整。
