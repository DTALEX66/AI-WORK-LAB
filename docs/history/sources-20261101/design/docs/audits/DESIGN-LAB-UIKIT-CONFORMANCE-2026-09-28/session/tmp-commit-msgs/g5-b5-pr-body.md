# G-5/B5：Evidence card append-only 约定（schema + 校验器 + 测试）

对应 FINAL TaskPack §B5（R13）：
> "Evidence append-only 约定（对应 R13）：evidence card 加 `supersedes` + immutable ID 校验（小改 `verify_evidence_cards`）。"

## 内容（2 commits，仅 3 文件）

1. **schema 层**（`c94fef0`）：`design-lab/schemas/visual-quality/evidence-card.schema.json` +2 可选属性
   - `evidence_id`：`^sha256:[0-9a-f]{64}$` — 记录实质字段的内容绑定身份
   - `supersedes`：同 pattern — append-only 修订指针（指向同 card_id 更早记录的 `evidence_id`）
   - 可选字段，`additionalProperties: false` 不变；现有 12 张 not-run 卡零改动

2. **校验器 + 测试层**（`2fafa69`）：`design-lab/scripts/verify_evidence_cards.py` + `design-lab/tests/test_evidence_cards.py`
   - `content_identity(card)`：实质字段（除 `evidence_id`/`supersedes`）的规范化 sha256；
     committed id 与内容不符 = 原地覆写 → fail closed
   - `accepted` 卡强制 `evidence_id`；带 `supersedes` 的修订强制 `evidence_id`；多记录链中每条记录强制 `evidence_id`
   - 每 `card_id` 分组形成一条线性链：唯一 genesis（无 supersedes）、无 fork / 无环 / 无 dangling / 无跨 `benchmark_id`；静默重复 `card_id` 仍非法
   - 记录数检查 `==` 放宽为 `>=`（append-only 允许追加修订），benchmark 集合覆盖检查不变
   - 测试 +10 用例（身份稳定 / genesis PASS / 线性链 PASS / 原地覆写 / accepted 缺 id / 修订缺 id / dangling / fork / 环 / 静默重复），**12/12 全绿**
   - 契约行加 `chained=` 计数（`EVIDENCE_CARDS_PASS cards=12 chained=0 ...`）；无下游消费者（grep 证实仅脚本自身 + 一份 2026-08-07 历史 handoff 文档提及，文档不解析契约行）

## 向后兼容

fixture `evals/evidence/evidence-cards.json` 未改动；12 张 not-run 单例卡无新字段 → 零误报：

```
$ python design-lab/scripts/verify_evidence_cards.py
EVIDENCE_CARDS_PASS cards=12 chained=0 human_calibration_required=true authoritative_accepts=0
```

## CI 接线

`verify_evidence_cards.py` 已在 `design-lab/scripts/verify_design_lab.py` 的 `SCRIPTS` 列表（Python gate 聚合内，随 PR 的 fresh clone 全量跑 12/12）；**无需 workflow 变更**。

## 证据分级

- **E1 STRUCTURAL**：schema 合同 + 静态校验（本 PR）
- 修订/append 的真实运行证据（E2/E3）不在本包范围；本包只封死"evidence 记录可被原地改写"的结构缺口

基线：`main@a6aeccf`（G-2 合并后）；本分支 2 commits，工作树 clean。
