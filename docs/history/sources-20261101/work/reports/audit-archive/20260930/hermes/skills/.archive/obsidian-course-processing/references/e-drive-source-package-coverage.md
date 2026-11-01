# E: drive source-package coverage accounting

Use this when the user asks “E盘数据源里还有多少课没有处理” or asks whether the raw `E:/学习数据` source corpus has been absorbed.

## Two separate counts

Always separate these two questions:

1. **Formal course verification count**
   - Source of truth: latest helper-repo audit JSON, usually `docs/course-local-verification-audit-YYYY-MM-DD.json`.
   - Report `courses_total`, `verified_by_available_methods`, and `needs_review`.
   - This answers: “正式课程库里还有多少门没核验完成？”

2. **E-drive source package mapping count**
   - Source of truth: live scan of `E:/学习数据` plus current formal-course source mappings.
   - This answers: “原始 E 盘课程包/资料包还有多少没进入系统映射？”
   - Do not infer this from formal course count alone: one formal course can cover many source packages, and one source category can be a parent/index rather than a single course.

## Package-root heuristic

Treat these second-level names as containers, not course names:

```text
单文件文档, 文档资料, 混合资料, 素材资产, 视频课程, 音频课程,
PDF文档, 图书合集, 电子书, Video
```

For paths under `E:/学习数据/<domain>/<container>/<child>`, count `<domain>/<container>/<child>` as one package-like root. If a file sits directly under a container, count the file path as a single-file package. Ignore `99_低价值暂存` and duplicate candidates unless the user explicitly asks to process them.

## Mapping method

1. Load latest audit JSON for formal status.
2. Scan package-like roots under `E:/学习数据`.
3. For each formal course under `E:/BaiduSyncdisk/Obsidian知识库/02_课程库`:
   - read its markdown;
   - collect concrete explicit source paths with the audit helper;
   - if explicit paths exist, map only those package roots;
   - otherwise use the same fuzzy source matcher threshold as the audit.
4. Compute:
   - total source package-like roots;
   - package roots covered by any formal course;
   - package roots covered by verified courses;
   - package roots covered by needs-review courses;
   - package roots not covered by any formal course mapping.

## Reporting format

Give both counts clearly:

```text
E盘源包未映射：N 个
正式课程未完全完成：M 门
```

Then list unmapped package roots. Explain that “unmapped source packages” and “needs_review formal courses” are different queues.

## Pitfalls

- Do not answer this from memory; rescan `E:/学习数据` and reload the latest audit JSON.
- Do not treat top-level domains such as `03_新媒体运营与增长` as one course.
- Do not treat container folders such as `视频课程` or `文档资料` as course packages.
- Do not collapse parent/category pages into completed courses just because child material exists.
- Do not call unprocessed packages “missing” until explicit source paths, source reports, and fuzzy aliases have been checked.
