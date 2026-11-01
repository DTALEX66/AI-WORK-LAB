# Root-spill diagnostics and OER crosswalk notes — 2026-07-02

## Root-spill pattern discovered

During a long Obsidian/TALOS session, two unexpected D: root entries appeared:

- `D:/OBS-V4-DEMO` — a synthetic V4 demo vault from helper-repo smoke testing.
- `D:/info@latest` — a small uni-app / Vue3 / Vite / `@uni-helper/unh` scaffold whose `package.json` had the abnormal project name `"/info@latest"`; no `.git`, no `node_modules`, no lockfile, no evidence of formal project use.

### Durable lesson

When the user asks “what is `D:\...`?” or flags a root-level spill, do not guess and do not delete immediately. Run a read-only triage:

1. Check exists/type/size/mtime/ctime.
2. If directory, list top-level files and sample up to max depth 2–3.
3. Detect whether it is a git repo, has lockfiles, `node_modules`, package manifests, or formal project markers.
4. Read only low-risk metadata files (`package.json`, `.npmrc`, `vite.config.js`, `README`, manifest/config files) to identify scaffold origin.
5. Search project workspaces for references before declaring it unused.
6. Classify as one of:
   - formal project/workspace,
   - generated demo vault,
   - scaffold/temp project,
   - cache/build artifact,
   - unknown — ask before moving/deleting.
7. If it is a demo/scaffold outside the user’s workspace convention, prefer moving to a workspace quarantine/demo folder or ask before deletion.

### Workspace convention reinforced

For Obsidian-Assistance helper smoke tests, do not create demo vaults at `D:/OBS-V4-DEMO`. Use:

`D:/All projects/Obsidian-Assistance/demo-vaults/OBS-V4-DEMO`

This avoids polluting D: root and matches the user’s “Projects under D:/All projects/” convention.

## V8/TALOS output placement pitfall

Daily Mission outputs must go under:

`00_主页/12_TALOS_Daily_Missions/outputs/`

Do not place output notes beside daily mission files at the top level, because scanners that glob `12_TALOS_Daily_Missions/*.md` can miscount outputs as missions. Tools should filter by `type: talos-daily-mission` or title containing `TALOS Daily Mission`.

## OER / open knowledge crosswalk pattern

The user asked to bring open knowledge / OER / collaborative knowledge sites into course conversion, retrieval, and cross-checking. Durable pattern:

1. Treat “open source knowledge website” as “open knowledge/OER/CC/public-domain resource” rather than software source code.
2. Verify official pages before writing claims. Prefer official pages for UNESCO OER, Wikimedia projects, Wikidata, MIT OCW, MDN, Stack Overflow licensing, Open Textbook Library, LibreTexts, etc.
3. Record source status explicitly; if a site returns 403 or cannot be fetched, mark it “待浏览器复核” instead of pretending it was verified.
4. Absorb structure and metadata first, not content copying:
   - Wikipedia → articles/categories/citations/version history.
   - Wikibooks/OpenStax/LibreTexts → textbook chapters, learning goals, exercises.
   - MIT OCW/Wikiversity → syllabus/readings/assignments/exams/projects.
   - Stack Overflow/Stack Exchange → question/answer/tags/votes/accepted answer.
   - Wikidata → entity/property/value/source/alias/language.
   - Commons/Wikisource/Gutenberg → media/text provenance, author, license, reuse metadata.
   - MDN → concept/syntax/examples/compatibility/reference.
5. For the formal vault, write an open-knowledge registry, structure matrix, and course crosswalk protocol; keep course facts grounded in local course sources and V6 evidence.

## Suggested vault artifacts

- `50_领域知识/开放知识与OER/open-knowledge-source-registry.json`
- `50_领域知识/开放知识与OER/00_开放知识源注册表.md`
- `50_领域知识/开放知识与OER/01_开放知识结构对比矩阵.md`
- `50_领域知识/开放知识与OER/02_课程转化交叉对比流程.md`
- `00_主页/15_TALOS开放知识交叉对比.md`
