# G-3 / B3：封死的 per-artifact QualityRecord schema + 校验器 + CI gate

对应 `docs/audits/DESIGN-LAB-CLOUD-AUDIT-2026-09-23-CROSSWALK.md` 的 **B3（R15）**。

## 为什么
Quality 三层（deterministic / automated_judge / human_jury）需要一个**物理不互相
覆盖**的 record schema + 校验器，且自动化 judge 不得产生假 model 分数、不得触碰
门禁。

CROSSWALK 是自认 NON-authoritative、"未读到仓内权威链" 的文档——它把 B3 标成
gap 时漏看了仓内已有的权威实现：`design-lab/src/design_lab/assurance/` 早已拥有
冻结的三层 *policy*（`qa_plane.py` 的 DETERMINISTIC/MODEL_ASSISTED/HUMAN 平面 +
证据上限 + `check_policy` 漂移守卫；`human_jury.py` 的冻结 APPROVE/REJECT + agent
不得签署；两个 schema + 400+ 行测试）。B3 真正缺的是 **record 层**——把三个平面的
payload 封进一条 per-artifact QualityRecord、字段物理分离、可校验（#143 判定
QualityScore 无数据源、未上 UI，正卡在这）。

因此本 PR 是 **compose 既有 assurance 包，不另起平行结构**（避免治理禁止的重复结构漂移）。

## 改动
- `src/design_lab/assurance/quality_record.py`：QualityRecord = 三个物理分离字段
  `quality.{deterministic, automated_judge, human_jury}` + 只读派生 `final_gate`。
  复用 `qa_plane.validate_finding` / `human_jury.assert_not_agent_signed`，不重新
  发明每层 payload。
  - 确定性层：`HARD_BLOCK` 一律 BLOCKED；
  - automated_judge：纯 advisory，永不填人字段、永不到达门禁（summary 视图里
    甚至没有 `blocking` key，比"空列表"更强）；
  - human_jury：APPROVE→PASS / REJECT→BLOCKED；无判决→NEEDS_HUMAN_VERDICT；
    PASS 在结构上无签名判决不可达。
- `design-lab/schemas/assurance-quality-record.schema.json`：封闭 JSON schema
  （每字段 `additionalProperties:false`）。
- `design-lab/scripts/verify_quality_record.py`：纯结构门（4 个可达 gate 态 +
  4 类对抗 record 必须被拒），登记进 `verify_design_lab.py` 的 SCRIPTS 链 →
  python-gate 每日 CI 执行。
- `design-lab/tests/test_assurance_quality_record.py`：17 项 hermetic 单测。
- `src/design_lab/assurance/__init__.py`：把新模块登记进包边界文档。

## 证据
- `python -m unittest design-lab.tests.test_assurance_quality_record` → **17 OK**；
  全回归 `test_assurance_{quality_record,jury,qa_plane}` + G-1 secret-history +
  G-2 sbom-lockfiles = **106 tests OK**。
- `python design-lab/scripts/verify_quality_record.py`（CI 口径）→
  `VERIFY_QUALITY_RECORD=OK`，exit 0。
- 纯 stdlib + jsonschema（仓内既有 schema 验证依赖，`verify_evidence_cards` 已同链在用）。
- 对抗保证：agent 签署的 human 字段 / 伪装成判决的 proposal / model finding 误入
  确定性层 / judge 单独给出 PASS——四类对抗 record 全部 fail-closed 被拒。