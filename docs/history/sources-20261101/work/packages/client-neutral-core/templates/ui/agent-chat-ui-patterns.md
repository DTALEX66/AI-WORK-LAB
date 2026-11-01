# Agent Chat UI Patterns

This template captures UI patterns for a Hermes Agent + CC Switch + Codex workflow surface. It absorbs assistant-ui and shadcn/ui ideas as **information architecture**, not as runtime dependencies.

## Runtime boundary

- Do not install React, Next.js, shadcn/ui, assistant-ui, Open WebUI, NextChat, Vercel AI Chatbot, database adapters, auth providers or telemetry from this template.
- Use it to guide future UI work in Hermes Desktop, the read-only Observer dashboard, or project-specific panels.
- Any real UI implementation must be visually inspected in a browser/desktop renderer before claiming it is polished.

## Layout

```text
┌─────────────────────────────────────────────────────────────┐
│ Top Bar                                                     │
│ Project · Branch · HEAD · Provider · Gateway · Session      │
├──────────────┬──────────────────────────────────────────────┤
│ Session List │ Agent Thread                                 │
│ / Runs       │  user / assistant / tool cards               │
│ / Cron       │  evidence callouts                           │
│ / Sleep      │  blocked/warning states                      │
├──────────────┴──────────────────────────────────────────────┤
│ Composer: prompt · attach context pack · mode · run button   │
└─────────────────────────────────────────────────────────────┘
```

## Required components

### Status rail

Use compact cards with explicit evidence state:

| Card | Required fields |
|---|---|
| Repo | root, branch, HEAD, dirty/clean, remote ahead/behind |
| Live Hermes | synced/unknown, last sync command, live provider/model redacted |
| Session | current session loaded, `/reset` needed, skills reloaded |
| Provider | provider/model, CC Switch proxy, live smoke marker if run |
| Codex | binary source, sandbox/read-only/write mode, worktree owner |
| Gateway | process running, platform configured, delivery target |
| Durable tasks | cron job id, sleep-mode state, last artifact path |

### Message thread

Message cards should distinguish:

- user message;
- assistant reasoning summary if visible;
- tool call request;
- tool result;
- verification evidence;
- warning / blocked / failed states;
- final user-facing answer.

Tool cards need:

```text
name · status · duration · exit code · artifact path · redaction status
```

Never display raw secrets, headers, `.env`, `auth.json`, session DB contents, raw traces or private prompts.

### Command palette

Use shadcn-style command palette vocabulary:

- Switch model;
- Run workflow doctor;
- Build context pack;
- Sync repo → live;
- Reload skills;
- Open gateway status;
- Create sleep-mode task;
- Run governance tests.

Every command entry must show whether it is read-only, writes repo, writes live Hermes Home, or can make network/model calls.

### Composer

Composer controls:

- mode: ask / code / review / sleep-mode / cron;
- context: current repo / context pack / selected files;
- execution: foreground / background notify / durable cron;
- risk badge: read-only / repo-write / live-config-write / network-model-call.

## Visual style

Default visual direction:

- Catppuccin Mocha tokens for long coding sessions;
- high contrast for warnings and blockers;
- monospace for command/evidence paths;
- compact cards, not large chat bubbles for tool output;
- strong status labels: `verified`, `unverified`, `blocked`, `failed`, `needs /reset`.

## Empty, loading and error states

- Empty state should explain what evidence is missing.
- Loading state should show the active tool/process, not a generic spinner.
- Error state should include next action and whether retry is safe.
- Blocked state should list the missing prerequisite rather than continue with guesses.

## Verification checklist

- Is repo/live/session layering visible?
- Is Gateway process separated from messaging platform delivery?
- Can the user see whether a result is suite green or ad-hoc verification?
- Are secrets and raw traces absent?
- Are long-running tasks represented as durable jobs or background processes with handles?
- Does the UI avoid implying context-pack generation is completed product work?
