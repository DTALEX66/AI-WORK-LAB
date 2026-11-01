# Vault Restructuring Pattern (2026-07-08)

## When to Use

When the user provides a detailed vault restructuring spec with:
- New numbered directory scheme (00_总控台, 10_课程库, 20_知识原子库, etc.)
- Course naming conventions (C0101, C0201, B1001)
- Source-root-mapped course skeletons
- Skeleton-only creation (no content conversion in the same pass)

## Execution Order

```
1. Scan raw disk → 2. Pre-execution report → 3. Create dirs → 4. Create skeletons →
5. Create nav → 6. Create templates → 7. Migrate old → 8. External links →
9. Execution log → 10. Verify → 11. Commit
```

All steps run in one session. Report counts at each step. Single commit at end.

## Course Skeleton Frontmatter

```yaml
---
type: course
course_id: C0101
title: 课程名称
domain: 01_设计课程
status: 待转化
source_root: "E:\\服务器\\设计课程\\..."
source_link: "file:///E:/服务器/设计课程/.../"
raw_source_readonly: true
tier: T2
content_status: 骨架
tags: [course, raw-source-linked]
---
```

## Old→New Course Mapping

When migrating old course content into new structure:
- Old: `02_课程库/Photoshop AIGC商业设计/00_课程总览.md`
- New: `10_课程库/01_设计课程/C0101/03_旧课程内容/00_课程总览.md`

The `03_旧课程内容/` subdirectory preserves old files. Later, promote key files to course root.

## T1/T2 Content Promotion

| Tier | Definition | Action |
|---|---|---|
| T1 | Has old content (00_课程总览.md, 模块总结, 术语索引) | Merge old body into new 00_课程主页.md; keep new frontmatter |
| T2 | Skeleton only | Generate 02_课程大纲.md from source directory scan |

T1 merge: old body > new body → keep new frontmatter (course_id, source_root, tier), use old body.
T2 outline: list subdirectories with file counts, video/PDF counts, first few filenames.

## Source Path Migration

When the raw disk changes (e.g. `E:/学习数据` → `E:/服务器`):
1. Never do blanket text replacement — subdirectory structures differ
2. Build a `dir_index` of all directories on the new disk
3. For each course, match `source_title` frontmatter against `dir_index`
4. Update `source_path` to the matched new path
5. Run audit to verify match scores

## OER Course Handling

OER courses (from awesome-skills-cn) get their own category: `11_OER开源技能库`.
Mark with:
```yaml
source_type: open-source-oer
source_repo: awesome-skills-cn
```
Add badge at top of page: `> 🔖 **开源知识组织** | 来源：awesome-skills-cn`

## Category Page Naming Convention

Data disk categories map to vault domains:
- `设计课程` ← `E:/服务器/设计课程`
- `记忆力与学习力` ← `E:/服务器/记忆力与学习力`
- `生活沟通` ← `E:/服务器/生活沟通`

Both vault directory names AND category frontmatter fields must match.
