# DESIGN-LAB HISTORY FREEZE & RETRIEVAL RULES

Authority: `DL-AUTHORITY-2026-09-18-R2`

未被 authority-index 明确标为 CURRENT 的旧/版本化记录，不是当前 Authority。

历史材料仅用于 lineage、decision rationale、residual comparison、evidence provenance、rollback/history。

已冻结家族：`docs/history/**`、`reports/history/**`、`docs/history/archive-2026-10-19/handoffs/**`、versioned ARCHITECTURE/ROADMAP/INTEGRATION/VISUAL_QUALITY、superseded taskpacks、old branch/completion/status reports。

特别冲突：PR #120 的 UCR 收口交接 自称 “tracked 权威交接”，但从 `DL-AUTHORITY-2026-09-18-R2` 起被明确降为 `HISTORICAL_EXECUTION_RECORD / NON_AUTHORITATIVE`。它的 branch 数已经过时，并引用一个未出现在远端 main taskpacks 目录的 UCR TaskPack，因此不得作为未来审计入口。该原件已于 2026-10-19 按 owner 指令从可见面删除，汇总面与逐份恢复句柄登记在 `docs/history/archive-2026-10-19/AGGREGATED-RECORD-2026-10-19.md` 与同目录 `REMOVALS.json`。

检索到旧文件时：先读 AUTHORITY -> 查 index -> 找 current replacement/crosswalk -> 对比 live code/CI -> 只保留历史用途。

禁止 mass-delete history。需要物理移动/删除时，必须先确认 replacement、callers、history preservation、hash/link update。
