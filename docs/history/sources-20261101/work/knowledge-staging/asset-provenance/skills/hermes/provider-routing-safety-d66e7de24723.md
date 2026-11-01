---
name: provider-routing-safety
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/software-development/provider-routing-safety/SKILL.md
---

---
name: provider-routing-safety
description: Use when routing API models through local routers.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
tags: [provider-routing, api-router, cc-switch, proxy, billing-safety, verification]
metadata:
  hermes:
    tags: [provider-routing, api-router, cc-switch, proxy, billing-safety, verification]
    related_skills: [model-switch, agent-workflow-fortress, hermes-runtime-auditing]
---

# Provider Routing Safety

## Purpose

Use this class-level skill when a user wants an API model routed through CC Switch, another local OpenAI-compatible gateway, a system proxy, or a provider adapter. Its purpose is to distinguish network reachability from actual model routing and to prevent accidental billable calls while configuration is ambiguous.

This skill complements, rather than replaces, the provider switching skill. The provider switcher owns model names and official commands; this skill owns route evidence, layer separation, and cost-aware stop conditions.

## Non-negotiable boundaries

- Never read or edit CC Switch databases, credential stores, OAuth files, `.env`, browser cookies, or raw provider configuration.
- Exception for structured READ-ONLY audits (user-requested "模型满血 / full-power" checks): open the CC Switch SQLite DB in URI read-only mode (`sqlite3.connect(f'file:{p}?mode=ro', uri=True)`), SELECT only structural/non-secret columns, and redact any key/token/secret/auth/password column values in output. Never write, never copy values of credential columns, never export the DB. See `references/cc-switch-full-power-audit.md`.
- Configure provider mappings through the user's controlled UI or official command. Never type or request API keys in chat or tool input.
- Do not treat a port, process name, `/health` response, HTTP 200, or UI label such as “enabled” as proof of a usable model route.
- Do not send a live completion, marker, retry loop, or diagnostic prompt while the route is unverified when the provider may incur charges.
- A system proxy port and an API Router are different capabilities. A proxy may forward traffic without exposing model inventory or usage accounting.

## Three-layer state model

Always report these independently:

1. **Active chat runtime** — the model/provider selected by the current session's runtime metadata. It may be frozen and differ from persistent config.
2. **Persistent Hermes config** — provider, model, and base URL written for future sessions. A config readback does not prove the current session changed.
3. **Router evidence** — process ownership, listener, health response, model inventory, mapping, and (only after explicit approval) a live request.

Never infer one layer from another. Require `/reset` or a new session after provider/model changes when the host application freezes session state at startup.

## Verification ladder

Use the cheapest, non-billable evidence first:

1. Identify the exact target router and its owner without reading private config.
2. Probe a local health endpoint, but record it only as liveness.
3. Probe the documented OpenAI-compatible inventory endpoint, usually `GET /v1/models`, without credentials. The result must be non-empty and contain the intended external model name or documented mapping.
4. Confirm the UI/provider mapping is saved and enabled. If the inventory is empty, stop; do not guess another port or rewrite Hermes.
5. Only after the user explicitly accepts possible usage, run one minimal live marker through the intended route. Record request model, response model, HTTP status, and route classification without recording secrets.
6. If the marker fails, revert to the previously known-good official provider rather than adding retries or fallback routes that can multiply cost.

## CC Switch-specific interpretation

- `127.0.0.1:7890` commonly denotes a system/network proxy in this environment; it is not automatically an OpenAI-compatible API endpoint.
- A listener owned by `cc-switch.exe` and a healthy HTTP response prove only that a local service is alive.
- `GET /v1/models` returning `{"models":[]}` means the API Router has no exposed model route. It is a hard stop for Hermes base-URL changes.
- A provider being enabled in one CC Switch screen does not prove that it is attached to the API Router model mapping. Verify the router inventory, not merely the provider list.
- Do not classify a local port as a “Codex router” or “API Router” from its number alone; verify the endpoint contract and process role.

## Safe configuration sequence

1. Preserve the current known-good Hermes provider/model.
2. Configure one provider/model mapping in the CC Switch UI.
3. Verify `/health` and `/v1/models` without secrets.
4. Confirm the intended model is present and the router's external name is stable.
5. Change only the intended Hermes lane through the official configuration command; do not overwrite credentials.
6. Read back provider/model/base URL with secrets redacted.
7. Start a new session or `/reset`; do not claim the existing session changed.
8. Run one approved smoke request and stop if it fails or the model response identity is not the requested model.

## Reporting contract

Use explicit statuses:

- `LIVENESS_ONLY`: process/health is reachable, model routing unproven.
- `ROUTER_UNCONFIGURED`: inventory is empty or mapping is missing.
- `ROUTER_READY`: non-empty inventory contains the intended mapping; no live inference yet.
- `LIVE_VERIFIED`: one approved request returned the requested route/model identity.

Always state what was not tested. Do not report “through CC Switch” from a health check alone.

## Pitfall: a 401 "invalid key" after the user changed the key is often NOT a wrong key

When a user reports `401 invalid api key` after editing their key, do not assume
the stored key is bad. Hermes (CLI and the desktop backend) loads credentials into
memory **at startup**; editing `.env` does not hot-reload a running process. If the
error's key tail exists in no file, or differs from the current `.env` tail, the
running process is holding the pre-edit value. Verify with a fresh subprocess
(`hermes chat --provider <P> -m <M> -q "Reply exactly: <MARKER>" -Q --toolsets safe`),
then the fix is simply restarting the Hermes app. Fingerprints (last 4 chars) only;
never print a key; do not kill the user's running desktop process yourself.
Full recipe: `references/api-key-401-stale-process.md`.

## Pitfall: KIMI K3 reasoning-model output truncation

When `kimi-k3` (or another KIMI reasoning model) returns HTTP 200 but `content`
is EMPTY with `finish_reason=length`, it is NOT a transient API error. The
model's `reasoning_content` consumes the same `max_tokens` budget as the final
`content`, so a long generation spends the whole budget reasoning and produces
nothing. Never loop-retry with the same parameters — either raise `max_tokens`
well above the artifact size AND shrink the ask, or move the task to a cheaper
non-reasoning model (DeepSeek) for long "just write it" implementation while
reserving KIMI for short core visual assets. See
`references/kimi-reasoning-model-truncation.md`.

## Related detail

See `references/ccswitch-api-router-verification.md` for the compact probe/evidence checklist and cost-safe stop conditions.
See `references/cc-switch-full-power-audit.md` for the read-only "模型满血" audit (providers/proxy_config structural query, reasoning_effort downgrade check, FULL_POWER/DEGRADED verdict format).
