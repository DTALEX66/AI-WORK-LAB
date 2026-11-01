# awesome-skills-cn / large skill-repository absorption pattern — 2026-07-03

## Trigger

Use this when the user names a large public skill repository or curated knowledge repository and asks to “吸收”, “提取知识”, “入知识库”, or “可以吸收下”. Example from this session: `lingxling/awesome-skills-cn`.

## What worked

- Treat the repo as an **open-source knowledge source**, not as code to install or execute.
- Verify source facts first via GitHub API / git metadata: `full_name`, `description`, `default_branch`, license, latest commit, file counts, and whether the recursive tree is truncated.
- For very large repos, avoid full clone as the primary path. If `git clone --depth 1` is slow or times out, use:
  - `GET https://api.github.com/repos/<owner>/<repo>` for repo metadata.
  - `GET https://api.github.com/repos/<owner>/<repo>/branches/<branch>` for commit SHA.
  - `GET https://api.github.com/repos/<owner>/<repo>/git/trees/<branch>?recursive=1` for file inventory.
  - `raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>` for selected Markdown files.
- Absorb **structure, categories, candidate indexes, and adaptation roadmap** instead of mirroring thousands of files into the vault.
- Keep explicit boundary language: candidate skill != installed/verified/trusted skill; do not run unknown scripts; do not treat open-source skill content as V6 course evidence.

## Vault write pattern

For large Agent/skill repositories, write a usage-layer node such as:

```text
50_领域知识/AI Agent技能库/
├── 00_<repo>吸收总览.md
├── 01_技能分类矩阵.md
├── 02_可吸收技能候选清单.md
├── 03_Hermes与Obsidian吸收路线.md
└── source-summary.json
```

Also update:

- `.obsidian/bookmarks.json` with a curated group such as `🧩 开源技能库`.
- `00_主页/00_TALOS_Home_Console.md` with a native wikilink entry.
- `93_导入报告/<date>_<repo>_absorption/` with a concise report and backups.

## Candidate extraction heuristic

Prioritize candidates that map to the user's recurring work:

- Obsidian / PKM / knowledge-base workflows.
- Agent orchestration, skill authoring, MCP/tool building, evaluation/memory.
- Git/GitHub, PR review, CI, coding agents, TDD.
- Search/research/OER/source verification.
- PDF/DOCX/OCR/speech/transcription/document conversion.
- UI/UX/design systems/frontend interface work.
- Productivity automation that can become a local tool or Hermes skill.

Down-rank unrelated shopping/transport/gaming/health/smart-home categories unless the user’s current task requires them.

## Validation checklist

- JSON parses: source summary and Obsidian configs.
- Markdown fences balanced.
- No mojibake markers.
- No accidental raw HTML from source descriptions; escape `<...>` in imported table text.
- Wikilinks resolve.
- Bookmark file paths exist.
- Commit only the absorption files and intended navigation updates; restore unrelated plugin runtime/EOL-only diffs.
- If a partial clone was attempted and failed, clean up the workspace-contained partial clone after the vault commit; if Windows locks a pack temp file, report it as cleanup state, not as a blocker to the vault ingestion.

## Pitfalls from the session

- `web_extract` may not be configured for GitHub page extraction; prefer GitHub API/raw URLs rather than relying on a browser scrape.
- A huge repo can time out during shallow clone. The durable pattern is not “clone failed”; the durable pattern is “switch to API tree + selected raw Markdown”.
- Source descriptions may include placeholders like `<url>` that look like HTML to Obsidian/checkers. Escape angle brackets in imported tables.
- Obsidian plugin config files may show unrelated EOL/runtime diffs. Check with whitespace-insensitive diff and restore if unrelated before staging.
