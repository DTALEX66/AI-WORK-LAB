# Auxiliary repo documentation/upload pattern (2026-07-01)

Use this when the user asks to整理项目经验、总结、上传到仓库 for the Obsidian knowledge-base helper project.

## Key distinction

- Real vault: `E:/BaiduSyncdisk/Obsidian知识库/` — never push/upload.
- Helper workspace: `D:/All projects/Obsidian-Assistance/` — may contain work/outputs/archive and is not necessarily a git repo.
- Helper repo: `D:/All projects/Obsidian-Assistance/github/Obsidian-Assistance/` — the GitHub repo to update/push.

If the workspace root is not a git repo, search for the nested helper repo rather than initializing or pushing the workspace root.

## Allowed content for helper repo

- Process documentation.
- Reusable scripts and templates.
- Skill/spec descriptions.
- CSS snippets or generic UI patterns.
- Data-boundary docs and project handoffs.
- Summaries of workflow lessons that do not quote course/vault content.

## Forbidden content

Do not commit/push:

- `.obsidian/` real config or vault notes.
- Raw course files, course PDFs, videos, audio, images, archives.
- ASR/OCR/transcript full text or intermediate outputs.
- `work/`, `outputs/`, `transcripts/`, `ocr/`, `asr/` directories.
- Private paths/configs beyond high-level path references needed for documentation.
- API keys, tokens, SSH keys, OAuth data, passwords, connection strings.

## Pre-commit safety checklist

Run a scoped check before committing:

```bash
git status --short
git diff --name-only
wc -c README.md docs/<new-doc>.md
# then ensure no changed paths match:
# .obsidian/|work/|outputs/|transcripts/|ocr/|asr/|\.sqlite|\.mp3|\.mp4|\.pdf|\.zip|\.rar|\.7z
# and scan changed docs for common secret patterns:
# API[_ -]?Key|token|secret|password|ssh|BEGIN .*KEY|AIza|sk-|ghp_|github_pat|Bearer
```

Only stage expected helper-repo docs/scripts. Prefer `git add README.md docs/<new-doc>.md` instead of `git add .`.

## Preserved todo / context compression pitfall

A preserved task list may show stale vault work in progress, such as a course deep-check. If the latest user message asks to整理项目经验/上传辅助仓库, the latest message wins:

1. Acknowledge the stale todo as irrelevant to the new task.
2. Do not resume the deep-check/course loop.
3. Work only in the helper repo.
4. Commit and push the helper repo only.

## Proven output shape

In the 2026-07-01 session, the safe deliverable was:

- `docs/project-experience-2026-07-01.md` — long-form脱敏 project experience summary.
- README docs index updated to point to the new file.
- Commit message: `docs: summarize obsidian assistance project experience`.
- Push target: `origin main` of `DTALEX66/Obsidian-Assistance`.

The final response should explicitly state that the real vault was not pushed and list the exact commit hash / changed files.
