# Open-Source Absorption Rules

Companion reference for `agent-workflow-fortress`. Read when absorbing an
open-source project, tool, MCP, or workflow idea into the portable pack. The
SKILL.md keeps the Core Loop + Safety Rules + Stack Boundary; these eight rules
govern WHAT to absorb and what to leave out.

## Absorb by design, not by copy-paste

For product/reference projects (RSSHub, FreshRSS, Karakeep, linkding, Linkwarden, Memos, NewsBlur, Tube Archivist, Aether-Radar), usually absorb:

- architecture pattern
- data model idea
- workflow checklist
- validation/test strategy
- UX principle

Do not automatically vendor their code or add them as runtime dependencies.

## Model/API-neutral harness absorption

When the user excludes models or non-free APIs, absorb only executor-independent workflow mechanics: Completion contract, Structured run state, Fail-closed safety, Single writer ownership, and Exact-tree evidence. Do not add a provider, model route, hosted endpoint, credential, external binary, telemetry path, or duplicate Hermes subsystem. Use `templates/task-tickets/model-neutral-agent-task.md` for execution tickets and load [`references/free-local-agent-harness-absorption.md`](free-local-agent-harness-absorption.md) for the full boundary and negative controls.

## Agent behavior evaluation absorption

When strengthening a portable Hermes Agent + CC Switch + Codex workflow pack, absorb promptfoo-style **declarative eval cases** for agent behavior boundaries, but do not default-install an eval runner or provider. Templates should remain model/provider neutral, use placeholders, avoid secrets/traces/raw private prompts, and write any run artifacts under project-local `.hermes/task-artifacts/evals/`. Good smoke cases cover repo/live/session layering, Gateway delivery layering, busy queue vs durable task execution, interrupted delegation evidence, Windows PowerShell selection, verification honesty, and secret/runtime boundaries. See [`references/agent-behavior-evaluation.md`](agent-behavior-evaluation.md).

## Context pack absorption

For new-session handoff, Codex/CC Switch review context, or context-overflow recovery, absorb repomix/gitingest-style **repo → LLM-friendly context pack** mechanics without default-installing their runtime or copying secrets. A context pack must be generated inside the target Git project, write only to a Git-ignored `.hermes/task-artifacts/` path, redact secret-like values, read only tracked allowlisted files plus Git metadata, and exclude `.env`, `auth.json`, `state.db`, sessions, logs, caches, dependencies, and `.hermes/` runtime data. Treat context-pack generation as handoff/evidence only; it is not real product work and must not count as a completed autonomous-loop task.

## UI/Skin absorption

For Hermes Agent + CC Switch + Codex visual workflow polish, absorb Catppuccin/shadcn-ui/assistant-ui ideas as **tokens and UI patterns**, not runtime dependencies. Keep skin presets under `templates/ui/`, terminal schemes under `templates/windows-terminal/`, and docs under `docs/workflow/`. Do not auto-install Open WebUI, NextChat, Vercel AI Chatbot, React/Next.js, component libraries, auth/database adapters, or telemetry. Do not auto-write Windows Terminal, VS Code, Hermes live config, provider/model, MCP, plugin, or approval settings. Treat skin templates as available-but-not-applied until config/readback or visual evidence proves activation. See [`references/ui-skin-absorption.md`](ui-skin-absorption.md).

## Local quality gate absorption

For Workflow-assistance-style portable packs, expose one canonical local gate command: `python services/orchestration/run_quality_gate.py verify`. Optional wrappers like `Justfile` may call that runner, but do not make `just` a default dependency or install it from setup/CI. The runner should be cross-platform, use argument lists rather than `shell=True`, stop on first failing gate, and print `QUALITY_GATE_PASS` / `QUALITY_GATE_FAIL` markers. Shell and PowerShell parsing gates may skip when their tool is unavailable; on Windows, avoid the `C:\Windows\System32\bash.exe` WSL shim and prefer Git Bash / GNU bash. PowerShell should prefer `pwsh` and only fall back to `powershell.exe`.

## Default-enable only if smoke-tested

Before adding any tool/MCP to default config, run the smallest real command:

```bash
node --version
npm view <package> version license repository.url
npx -y <package> --help
```

If it errors on the current environment, document it as optional and include the enable condition.

For MCP candidates, first run `python packages/client-neutral-core/scripts/mcp_candidate_audit.py --write-template <ignored-artifact.yaml>` and audit the filled file. A passing candidate audit means the metadata is complete, not that the MCP is configured, running, safe, or default-enabled. Candidate files must document pinned package/version, repository, license, data externality, permissions, native Hermes overlap, distinct advantage, smoke evidence, and prompt schema budget.

## Avoid duplicate capability

If Hermes already has a native tool, do not add an MCP that exposes the same permission unless it adds a real advantage:

| Native Hermes capability | Avoid default duplicate |
|---|---|
| `memory` tool | memory MCP |
| `file` tools | filesystem MCP |
| `browser` / `computer_use` | browser MCP unless needed |
| `web_search` / `web_extract` | search wrappers without clear gain |
