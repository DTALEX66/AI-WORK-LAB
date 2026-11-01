# Reports boundary

This directory contains dated audit reports and delivery snapshots. They are immutable historical records of the tree, runtime, and authorization state named inside each report; they are not the current capability index.

## Current-truth rule

For current project status, use these normative sources in this order:

1. `design-lab/config/capability-evidence-index.json`
2. `design-lab/config/capability-status.json`
3. `design-lab/scripts/verify_design_lab.py`
4. `design-lab/scripts/verify_release_gate.py`
5. `docs/current/ROADMAP.md`

Whether a record in this directory is still true of the checkout you are reading it from is a
separate question, and it now has an answer that does not require trusting the prose:
`GET /api/evidence-projection` (contract `design-lab/schemas/evidence-projection.schema.json`,
emitter `src/design_lab/governance/evidence_readback.py`) re-derives, for every ledger record,
whether its bytes still reproduce and whether it still describes the current subject. A dated
report that the projection marks `verified=false` or `current=false` is history, not status.

A report's E3/E4/E5 wording is historical evidence only unless the current capability index independently binds the same claim to the current checkout with the required runtime, provenance, read-back, human, or exact-SHA evidence. These reports are **not current runtime proof**. In particular, historical reports mentioning ComfyUI or MiniMax H3 do not override the current E0 placeholder state.

Do not edit a dated report to make it appear current. Add a new dated report with an exact tree, runtime identity, and evidence handles when a capability is genuinely requalified.


## 目录布局（DL-MIG-004）

- `reports/current/` — 当前基线、治理报告与交付物（DL-* 命名）。每个 `.json`
  顶层含显式 projection provenance 键（`projection: true`、`subjectSha` 生成时的
  HEAD 40hex、`fresh: false`、`generatedBy`）：`current` = latest projection，
  `fresh=false` 表示这是某一刻的投影，不是实时真值——re-validate against live
  tree/CI before relying on it。少数由 `scripts/generate_current_reports.py`
  字节锁定的投影（`src/design_lab/governance/reporting.py`）改以自带的
  `fresh`/`freshnessMeaning`/`subjectSha` 键承担同等语义，不再叠加顶层键以免
  破坏其 `--check` 字节门禁。
- `reports/history/` — 历史 V4/V42/ODA4 报告与按日期命名的交接摘要（不可篡改归档，不改写）。
  2026-10-19 起 `reports/` 根级不再放任何按日期命名的 handoff；全部整目录归入此处。
  当前接续入口是 `docs/current/NEXT-AGENT-PROMPT.md`，不是任何历史 handoff。
