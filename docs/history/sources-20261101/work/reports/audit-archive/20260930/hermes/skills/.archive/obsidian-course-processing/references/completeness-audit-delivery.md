# Completeness Audit & 100% Delivery Pattern

## Trigger words
"想办法完成它", "全部开始", "全部覆盖", "继续", "100%交付"

## 7-Dimension Audit Table

| 维度 | 检测规则 | N/A条件 |
|---|---|---|
| PDF文本 | `03_逐节总结/` has non-ASR `.md` files >100B | 素材型/纯视频课程 |
| ASR转写 | `03_逐节总结/` has `*ASR*.md` files >100B | PDF/古籍类无视频 |
| 视觉索引 | `12_视觉索引与配图.md` exists >200B | — |
| 外部链接 | `00_课程主页.md` contains `http` | — |
| 内部导航 | `00_课程主页.md` contains `[[` | — |
| Dataview | `00_课程主页.md` contains `dataview` | — |
| 验证页 | `06_验证与不确定项.md` exists >100B | — |

## Scoring

```python
applicable = [dim for dim in dimensions if dim is not N/A]
achieved = [dim for dim in applicable if dim is True]
score = achieved * 100 // len(applicable)
```

## Delivery Workflow

1. Scan all gaps — iterate every course, check each dimension
2. Fix N items — for any "N" in applicable dimension, force-fix
3. Regenerate audit sections — embed completion table with score
4. Verify — all courses must show `完成度: 100%`
5. Commit once

## User Signal Patterns

- "全部开始/一次性解决" = ALL pending at once, no confirmation
- "继续" = resume ALL unfinished threads autonomously
- "想办法完成它，不管什么办法" = deliver, don't explain limitations

## Content-Matched Screenshot Pattern

- Terms from `03_逐节总结/*.md` body (NOT `00_课程主页.md` frontmatter)
- Match terms to PDF pages → extract page as PNG
- Embed in course page: `![[99_附件_重组/内容匹配截图/...]]`
- Material-type courses: skip (N/A)

## Authoritative Link Cross-Check

Dispatch 3 subagents covering ~20 courses each, batch-apply results.
