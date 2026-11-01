# Authoritative Link Delegation Pattern

When the user requires every course to have cross-verified external links:

## Trigger
User says "所有课程是否都有交叉对比分析与对应权威链接" or similar.

## Pattern
1. **Split courses into 3 groups** (~20 per group) by category domain
2. **Dispatch 3 leaf subagents** via `delegate_task(tasks=[...])` in parallel
3. Each subagent uses `web_search` for each course's domain + key concepts, returns links + verification status
4. After all complete, parse subagent output files and apply links to course pages in one batch

## Application
After subagents return, apply links to each course's `00_课程主页.md` under `## 权威参考（全网交叉验证）`. Also update `06_验证与不确定项.md`.

## Pitfalls
- **DuckDuckGo won't extract**: Set `web.extract_backend` to a non-ddgs backend, or use browser for verification.
- **Don't fabricate links**: Only use links subagents actually verified as accessible.
