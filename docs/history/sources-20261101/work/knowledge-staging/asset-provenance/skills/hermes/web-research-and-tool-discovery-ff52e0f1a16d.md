---
name: web-research-and-tool-discovery
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/research/web-research-and-tool-discovery/SKILL.md
---

---
name: web-research-and-tool-discovery
description: "Use when sweeping the web for tools to absorb."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, linux, macos]
metadata:
  hermes:
    tags: [research, search, github, huggingface, tools]
---

# Web Research & Tool Discovery

Use when the user asks to sweep the web for tools, frameworks, best practices,
or workflow enhancements ("去全网找找 / 搜索可吸收内容"). Discover real,
usable artifacts — not article summaries.

## Order of preference (tool discovery first)

1. **GitHub search** — real tools with stars, far more actionable than blogs.
2. **Vendor docs / llms.txt** — authoritative statements (e.g. learn.chatgpt.com,
   developers.openai.com/llms.txt).
3. **Search engines** — only for leads, with the workarounds below.
4. **HuggingFace** — models/courses/spaces; frameworks live on GitHub.

## Engine pitfalls (Windows, 2026-08-12 verified)

- **Bing**: an English query with no locale returns Chinese dictionary spam
  (baike/cambridge). Force `&mkt=en-US&setlang=en` or use a different engine.
- **DDG html**: `https://html.duckduckgo.com/html/?q=...` works but rate-limits
  fast (empty results after a few queries). Space queries out and retry.
- **zhihu/cn blog results** often dominate CN-region queries; prefer GitHub
  search for tool discovery.

## GitHub search

- Use the native CLI, NOT the REST search endpoint:
  `gh search repos "agent orchestration" --sort stars --limit 8 --json fullName,stargazersCount,description`
  (`gh api search/repositories -f q=...` returned 404 in practice).
- Known framework stars: `curl -H 'Accept: application/vnd.github+json' -H 'User-Agent: research' https://api.github.com/repos/<owner>/<repo>`
  (unauthenticated public API is fine; `gh api repos/<owner>/<repo>` also works).
- Filter by usefulness to the actual task; report star + one-line capability.

## HuggingFace

- Direct connections time out (HTTP 000); route through the user's local proxy:
  `curl -x http://127.0.0.1:7890 https://huggingface.co/api/models?search=agent&sort=downloads&direction=-1&limit=8`
- API endpoints: `/api/models?search=X&sort=downloads`, `/api/spaces?search=X&sort=likes`.
- HF value is mostly models/courses (e.g. agents-course); orchestration
  frameworks are on GitHub — say so instead of padding the report.

## Output shape for enhancement sweeps

When the user wants candidates absorbed into a project:

1. Table: tool/star/capability → mapping to a concrete gap in the project.
2. Exclude the category the user excludes (e.g. gates/verification).
3. Rank by value-to-project; give landing paths, not just a list.
4. Ground every claim: URL, star count, or doc quote. Mark unverified sources
   as "community report, unconfirmed" (see agent-update-safety evidence levels).
