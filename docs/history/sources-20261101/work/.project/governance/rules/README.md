# Rule precedence

Root rules define safety, approval, evidence and cross-module boundaries. Module
rules may narrow permissions but cannot weaken root rules. Task-specific cards may
narrow them further. Conflicts stop as `BLOCKED`; there is no silent fallback.
