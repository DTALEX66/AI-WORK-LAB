# UI/Skin Absorption

Workflow-assistance absorbs UI/skin projects as **portable visual guidance**, not as default runtime dependencies.

## Sources

- `catppuccin/catppuccin` — palette tokens and semantic color roles
- `catppuccin/windows-terminal` — Windows Terminal color scheme shape
- `shadcn-ui/ui` — component vocabulary, settings panel, command palette, status card patterns
- `assistant-ui/assistant-ui` — assistant thread, composer, action state and tool-call timeline patterns

## Local artifacts

- `docs/workflow/ui-skin-system.md`
- `templates/ui/skin-presets.yaml`
- `templates/ui/agent-chat-ui-patterns.md`
- `templates/ui/terminal-theme-checklist.md`
- `templates/windows-terminal/catppuccin-mocha.json`

## Boundaries

Do:

- Keep presets as token/template files.
- Keep Windows Terminal schemes copyable but not auto-applied.
- Distinguish Hermes `display.skin`, terminal color scheme, VS Code theme, Desktop/dashboard UI and project-specific web UI.
- Require visual/readback evidence before claiming a skin is active.
- Use status roles for repo/live/session, provider, Codex, Gateway, durable tasks, tool calls and verification evidence.

Do not:

- Install React, Next.js, shadcn/ui, assistant-ui, Open WebUI, NextChat, Vercel AI Chatbot or component libraries by default.
- Modify Windows Terminal `settings.json`, VS Code settings, Hermes live config, provider/model, MCP, plugin, approval or credential state without explicit user direction.
- Treat a theme template as applied skin.
- Use color alone for blockers, warnings or verification state.
