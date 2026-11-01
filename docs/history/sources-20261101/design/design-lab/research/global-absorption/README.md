# Global Design Knowledge Absorption Registry

This directory is the controlled intake layer for external design knowledge, open-source projects, standards, and research.

## What this registry prevents

- Blindly copying third-party repositories.
- Mixing trademarked brand assets into generic design systems.
- Loading untrusted `SKILL.md` instructions directly into an agent.
- Treating popularity as evidence of quality.
- Losing attribution or per-file license information.
- Turning a design assistance repository into an unmaintainable vendor dump.

## Integration modes

| Mode | Meaning |
|---|---|
| `vendor-adapt` | Small schemas or rules may be copied and adapted with attribution and license notices. |
| `adapter` | Keep the source external; integrate through a pinned CLI, package, MCP, or file-format adapter. |
| `derive` | Extract general method and rewrite locally; do not copy substantial wording or branded assets. |
| `reference` | Keep a source link and compliance mapping; the source remains authoritative. |
| `quarantine` | No runtime use until license, provenance, security, and quality review are complete. |

## Admission gate

A source may enter production context only after:

1. Identity and canonical repository/site are confirmed.
2. License and trademark boundaries are recorded.
3. Skill text is inspected for semantic supply-chain attacks.
4. OpenSSF/OSV or equivalent checks are recorded where code is used.
5. A source-grounded extraction note identifies what was absorbed.
6. At least one benchmark shows improvement over the no-source baseline.
7. The source has an owner, version pin, review date, and removal path.

Registry snapshot: 2026-08-04. It is intentionally a curated high-recall starting point, not a claim that every website on the internet has been copied.


## v3 治理状态（DL-KNW-003，2026-08）

遗留 162 条登记已逐条迁移/隔离至 `QUARANTINE_REGISTRY.json`（fail-closed，不批量制造字段）。
`SOURCE_REGISTRY.json` 为 v3 活动登记（仅完整人工审核 SourceRecord 可进入）。
隔离登记不得进入能力加载、模型上下文或 reviewed 状态；提升需人工补齐缺失事实。
