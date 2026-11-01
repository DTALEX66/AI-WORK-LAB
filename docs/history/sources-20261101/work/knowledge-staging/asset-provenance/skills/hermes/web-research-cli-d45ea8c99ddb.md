---
name: web-research-cli
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/research/web-research-cli/SKILL.md
---

---
name: web-research-cli
description: "Use when researching tools or upstream status via terminal."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [research, github, huggingface, search, absorption, orchestration]
    related_skills: [skill-library-curation, agent-workflow-fortress]
---

# Web Research via CLI

Use when asked to "全网找找/搜搜" for tools, frameworks, upstream issues, or
patterns to enhance or absorb into a project (user phrasing: "除了门禁验证类的
其他的都搜搜"). Validated 2026-08-12 on a full agent-orchestration sweep.

## User rules for this class of task

- Exclude gate/verification/CI-benchmark material unless explicitly included
  ("门禁验证类不要"). Evaluation leaderboards, CI gates, exact-SHA tooling are
  out of scope by default.
- Absorption lands on the **global workflow layer**, not only the current repo:
  implementation layer (module code) + runtime skills (Hermes) + live sync
  (Codex). Declare the three surfaces in the plan doc and keep consumer projects
  using the module API instead of copying code.
- Deliver a tracked plan doc (sources with stars/URLs, per-item landing path,
  acceptance criteria, status checkboxes), then implement per item.

## Search order (most reliable first)

1. **GitHub search — use `gh search repos`, not `gh api search`**.
   `gh api search/repositories -f q=...` returned 404 on this setup; the native
   command works:
   ```bash
   gh search repos "agent orchestration workflow" --sort stars --limit 8 \
     --json fullName,stargazersCount,description
   ```
   Known frameworks: `curl -s -H 'User-Agent: research' -H 'Accept: application/vnd.github+json' \
     https://api.github.com/repos/{owner}/{repo} | jq '{full_name, stargazers_count, description}'`
   — public API needs no auth and beats guessing star counts.
2. **Upstream issue status** (is this a known bug?): `gh api repos/{owner}/{repo}/issues/{n} --jq '{state, title, created_at}'`.
   A matching OPEN issue with the same version line = "official known, not a
   local anomaly" answer.
3. **Search engines last** — both major engines are hostile to scripted queries:
   - DuckDuckGo html endpoint rate-limits after a few queries (empty results);
     space queries out or switch source.
   - Bing without `mkt`/`cc` parameters returns Chinese dictionary spam for
     English queries (`&mkt=en-US&cc=US` forces English results).
   - If a search result page is useless, drop it and go back to GitHub search —
     it is the higher-signal source for tooling questions.
4. **HuggingFace** — direct `huggingface.co` may time out from this machine;
   use the system proxy and a UA:
   ```bash
   curl -s -x http://127.0.0.1:7890 -H 'User-Agent: Mozilla/5.0' \
     'https://huggingface.co/api/models?search=agent&sort=downloads&direction=-1&limit=8'
   ```
   HF value is mostly models/courses/leaderboards — frameworks live on GitHub.
5. **Article scraping** — `curl -sL` + Python regex strip (`<script>/<style>/<[^>]+>`)
   works when the page exists; if a blog 404s or the structure is empty, do not
   burn time — fall back to GitHub API metadata for the same topic.

## Pitfalls

- **Terminal goes through the project-data-boundary guard**: raw commands and
  shell chaining (`;` `&&` `>` pipes) are blocked. Wrap every call as
  `python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- <cmd>`
  (HERMES_HOME = `C:/Users/<user>/AppData/Local/hermes` on Windows) with the Git
  project as workdir, and write fetches to `.hermes/task-runtime/tmp/` via
  `curl -o <project-relative>` — the wrapper spawns curl, so `-o` is a child
  argument, not shell redirection, and passes the guard.
- **Inline `python -c` regex gets false-flagged**: a one-liner containing
  `</script>`-style sequences (HTML stripping) is blocked as "absolute POSIX
  path outside the Git project". Write the extractor script with write_file into
  `.hermes/task-runtime/tmp/extract.py` and run it through the wrapper instead.
  Same for GitHub search JSON: curl to a file, then parse with a small script
  file (working extract/parse recipe in `windows-development-environment` skill
  → `references/pnpm-windows-dependency-management.md`).
- `gh api search/repositories` 404 is a parameter-shape issue — switch to
  `gh search repos` instead of debugging the API form.
- Bing without region params returns dictionary/百科 noise; check the first
  result titles before trusting any.
- `curl` through the system proxy is required for HF on this machine; a bare
  `HTTP 000` after ~20s means proxy, not HF being down.
- When writing research outputs to files from Git-Bash, use Windows-native
  absolute paths (see windows-development-environment: `/tmp/x.md` resolves to
  `<cwd>\tmp\x.md` for native Python, not the temp dir).
- Star counts and "official known issue" answers are evidence — record both the
  URL and the star/issue number in the plan doc so the verdict is auditable.
