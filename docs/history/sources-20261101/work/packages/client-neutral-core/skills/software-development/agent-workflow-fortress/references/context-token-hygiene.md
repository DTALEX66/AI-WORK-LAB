# Context and Token Hygiene

Companion reference for `agent-workflow-fortress`. Read when Codex/Hermes
reports "local token/context is too large" or when cleaning up a bloated
project runtime. Distinguish the four different things before deleting anything.

## The four token/context meanings

1. **Credential token** — API/OAuth secret; never print it and do not confuse it with model usage.
2. **Active context tokens** — system instructions, tool schemas, conversation items, and tool outputs; this is what can overflow a model request.
3. **Session database size** — searchable history on disk; it is not automatically injected in full and should normally be preserved.
4. **Cache/log/dependency size** — disk usage only; deleting it does not shrink the already-built active request.

## Required workflow

1. Parse the newest failed request dump structurally and report only counts/character sizes by component. Do not print headers, bodies, credentials, or raw conversation text.
2. Inspect project context files (`.hermes.md`, `AGENTS.md`, `CLAUDE.md`, `.cursorrules`) and identify which one is actually auto-loaded. Do not blame every repository document.
3. Create a concise, non-auto-loaded current handoff before cleanup. Preserve user requirements, verified baseline, unresolved work, recovery paths, and authoritative reports.
4. Delete only regenerable or absorbed artifacts: failed request dumps, oversized terminal-result blobs, stale screenshots, orphan temp snapshots, old delegation summaries already represented in the final report, and rotated logs.
5. Preserve `state.db`, Git data, current logs, runtime dependencies, skill indexes, unique audit evidence, and current delegation reports unless the user explicitly authorizes history loss.
6. Configure earlier compression through the official CLI and verify the live config. Do not hand-edit secrets or assume the setting changes the already-running request.
7. Explain that disk cleanup cannot shrink the current conversation; begin a new session and load only the concise handoff.

Never use `git clean -fdX` or broad cache deletion around an installed Hermes tree: `venv`, `node_modules`, model metadata, and current terminal snapshots may be runtime dependencies rather than junk.
