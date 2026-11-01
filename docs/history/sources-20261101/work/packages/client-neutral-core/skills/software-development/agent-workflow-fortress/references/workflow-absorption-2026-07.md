# Workflow Absorption Session Notes — 2026-07

## Durable lessons

- User may redirect from a domain-specific plan to a meta-workflow plan. In one session the user deferred an Obsidian knowledge-base track as a later concern and asked for Hermes workflow strengthening instead. Respect that boundary while still extracting reusable, domain-neutral workflow assets.
- For "is there anything else left to absorb?" questions, do not answer from memory. Search both prior sessions and the current deployment repo, then classify findings as absorbed / missing / deferred / candidate.
- Prefer absorbing open-source projects by pattern unless the runtime package is small, safe, licensed, and smoke-tested. Product references such as RSSHub, FreshRSS, Karakeep, linkding, Linkwarden, Memos, NewsBlur, Tube Archivist, Aether-Radar, MINIGAME, and Star-Trails-Log often contribute architecture, UX, validation, and loop patterns rather than vendored code.
- Default-enable MCPs only after a real smoke test. If a package fails because of Node/runtime compatibility, document the enable condition instead of hard-coding a broken default.
- Avoid duplicate capability: do not add Memory/FileSystem/browser MCPs by default when Hermes native memory/file/browser/computer tools already cover the need.
- When adding prompt/rule templates, add a safety scanner if possible; ensure the templates themselves pass the scanner by avoiding literal dangerous command/injection examples.

## Concrete absorption pattern used

1. Search session history for prior comparison/absorption/source names.
2. Inspect repo for existing markers and stale references.
3. Smoke-test candidate MCP packages.
4. Enable only working defaults; document candidates and blockers.
5. Add a class-level workflow skill, not one-off session skills.
6. Add templates for AGENTS/CODEX/SECURITY/DESIGN and task tickets.
7. Add a prompt/rule scanner script.
8. Validate YAML, skill frontmatter, security scan, MCP smoke test, and git status before reporting.

## Candidate handling example

- `@modelcontextprotocol/server-sequential-thinking`: historical smoke result only; retired from the default stack because it overlaps native reasoning and workflow skills.
- `@upstash/context7-mcp`: useful for library docs, but only enable after Node >= 20 if current runtime lacks required web stream globals.
- `@playwright/mcp`: useful when native Hermes browser/computer tools are insufficient; enable after Node >= 20 and a local smoke test.
- MarkItDown/OpenDataLoader/Cognee/GBrain/Talos: defer when current scope excludes knowledge-base/Obsidian ingestion.
