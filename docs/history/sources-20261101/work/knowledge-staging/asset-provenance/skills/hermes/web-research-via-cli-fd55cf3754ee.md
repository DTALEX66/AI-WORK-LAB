---
name: web-research-via-cli
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/research/web-research-via-cli/SKILL.md
---

---
name: web-research-via-cli
description: "Use when researching topics or tools across the web via CLI."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows, macos, linux]
metadata:
  hermes:
    tags: [research, web, github, huggingface, search, survey, tool-evaluation]
    related_skills: [grounded-citations, content-accuracy-crosscheck, github-repo-management]
---

# Web Research via CLI (tech survey, tool evaluation, fact checking)

Use when the user asks to research across the web: "找找有什么能增强 X 的",
"查查其他安装渠道/官方文档", "GitHub 上有没有人遇到这个问题", comparing
tools/frameworks, or verifying claims against official sources. Goal: a
ranked, source-backed answer — not a search-engine dump. This skill is the
CLI-side companion to `grounded-citations` (citation formatting) and
`content-accuracy-crosscheck` (content verification).

## Pipeline (validated 2026-08-12)

1. **Check local evidence first** (the machine is often the primary source):
   `Get-AppxPackage OpenAI.Codex`, `ls ~/.codex`, mtimes, `codex --version`,
   process trees. Only go to the web for what the machine cannot tell you.
2. **Prefer direct sources over search engines**: known doc roots
   (learn.chatgpt.com/docs/*.md, developers.openai.com/llms.txt,
   repo-specific `llms.txt`), GitHub issues/PRs, and official API endpoints.
   `llms.txt` files give clean, parseable doc indexes.
3. **GitHub is the most reliable search surface** — use the native CLI, not
   the REST search API (see pitfalls).
4. **HuggingFace needs the proxy** on this machine (see pitfalls).
5. **Synthesize into a table** with source links + a verdict, and offer to
   archive the finding into the project (tracked doc) when the user says
   "吸收到项目里".

## Reliable commands

```bash
# DuckDuckGo HTML (no JS needed; REQUIRES a real UA or it returns empty)
curl -s -m 30 'https://html.duckduckgo.com/html/?q=<urlencoded>' \
  -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)' \
  | python -c "import sys,re,html; t=sys.stdin.read(); \
    [print(html.unescape(re.sub(r'<[^>]+>','',t2))[:80], '\n ', u[:110]) \
     for u,t2 in re.findall(r'<a[^>]*class=\"result__a\"[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>', t)[:8]]"

# GitHub native search (repos): reliable star-ranked tool discovery
gh search repos '<query>' --sort stars --limit 8 \
  --json fullName,stargazersCount,description

# GitHub issues: community confirmation that a bug/behavior is known
gh api "search/issues?q=repo:<owner>/<repo>+<terms>" \
  --jq '.items[] | "#\(.number) [\(.state)] \(.title[0:70]) (\(.created_at[0:10]))"'

# GitHub public REST (no auth): star counts for known repos
curl -s -H 'User-Agent: research' -H 'Accept: application/vnd.github+json' \
  https://api.github.com/repos/<owner>/<repo>   # -> .stargazers_count, .description

# HuggingFace (proxy required): libraries/models by downloads
curl -s -m 30 -x http://127.0.0.1:7890 -H 'User-Agent: Mozilla/5.0' \
  'https://huggingface.co/api/models?search=<term>&sort=downloads&direction=-1&limit=8'
# HF Spaces similarly: /api/spaces?search=...&sort=likes

# Raw page text for analysis (strip scripts/styles/tags)
curl -s -L -m 40 -H 'User-Agent: Mozilla/5.0' '<url>' \
  | python -c "import sys,re,html; t=re.sub(r'<script[^>]*>.*?</script>|<style[^>]*>.*?</style>|<[^>]+>',' ',sys.stdin.read(),flags=re.S); print(html.unescape(re.sub(r'\s+',' ',t)))"
```

## Pitfalls (each cost real time on 2026-08-12)

- **Bing search returns Chinese dictionary/encyclopedia junk** for English
  queries from this network (region redirect). Do NOT waste a batch on
  `www.bing.com/search`. Use DDG HTML or GitHub API instead; if you must use
  Bing, force `&setlang=en&mkt=en-US`.
- **`gh api search/repositories` 404s** with `-f q=...`; the working form is
  the native `gh search repos` command, or
  `gh api 'search/repositories?q=...&sort=stars'` (URL query string).
- **HuggingFace is unreachable direct** (timeout HTTP 000); route via the
  local system proxy `-x http://127.0.0.1:7890` (FlClashCore). Do NOT kill
  the proxy core to "test" — it is not auto-restarted.
- **Search engines are the slow path.** If the topic maps to a known project
  (openai/codex, langchain-ai/langgraph), hit GitHub API / issues directly.
- **Don't re-diagnose known issues**: after finding a matching GitHub issue,
  check its state/comments for an official answer before continuing research.
- When the user says "门禁验证类的不要" (exclude CI-gate/verification
  topics), filter those categories up front — evaluation benchmarks, CI
  gates, quality gates, exact-SHA tooling.

## Archive habit

When the user says "加入归档/吸收到项目里/上传云端": write the findings as a
tracked doc under the project's archive directory (e.g. `50-taskpacks/`),
commit on a branch, open a PR, merge on green CI, then verify
local==remote HEAD. Keep session-specific research in the repo archive —
not in memory.
