# Validated project-local Codex integration pattern

## Repository changes

- Extend the repository root `AGENTS.md` with the active owner, read-only projection boundaries, single-writer rule, runtime evidence paths, and canonical gate.
- Add a narrow project-local Codex skill under `.agents/skills/<class>/SKILL.md` when Codex needs a discoverable workflow procedure.
- Keep user-owned Codex routing, authentication, Desktop state, sessions, MCPs, plugins, and unrelated skills unchanged.
- Do not promote project-specific module names or ledger ownership into the global user layer.

## Official discovery boundary

Current Codex discovery surfaces are:

```text
User guidance:  $CODEX_HOME/AGENTS.md
Project rules:  <project>/AGENTS.md
User skills:    $HOME/.agents/skills/<name>/SKILL.md
Project skills: <project>/.agents/skills/<name>/SKILL.md
Command rules:  $CODEX_HOME/rules/*.rules
```

Do not use `.codex/skills` for current user or project skills. A smoke that explicitly tells Codex to read a file at that old path is not automatic-discovery evidence.

## Discoverability smoke

From the target repository, start a fresh real Codex task in a read-only sandbox. Ask it to report the applicable project rules and available project skill by name without supplying the skill's path in the prompt. Record only bounded results: discovered rules, ownership boundaries, and the canonical verification command. Do not preserve session bodies, prompts, responses, or credentials.

## Evidence boundary

A project-local smoke proves only project-rule and project-skill discoverability. It does not prove arbitrary-project global readiness, provider routing, credentials, Desktop state, live apply, exact-SHA CI, publication, or release readiness. Verify each through its owning contract. For global readiness use the separate user-overlay canary in `codex-global-user-overlay.md`.
