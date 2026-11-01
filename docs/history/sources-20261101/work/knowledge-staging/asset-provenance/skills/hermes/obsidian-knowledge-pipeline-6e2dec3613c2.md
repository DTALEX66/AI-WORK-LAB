---
name: obsidian-knowledge-pipeline
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: hermes
archived_at: 2026-08-21
source_path: C:/Users/ALEX/AppData/Local/hermes/skills/note-taking/obsidian-knowledge-pipeline/SKILL.md
---

---
name: obsidian-knowledge-pipeline
description: "从原始课程素材（音频/视频/PDF）到 Obsidian 知识库的全自动处理管线：转写、OCR、核验、总结、卡片、内容过滤、导入报告、UI 配置。"
tags:
  - obsidian
  - pipeline
  - course-processing
  - knowledge-base
  - content-filtering
  - windows
related_skills:
  - obsidian
  - windows-development-environment
---

# Obsidian 知识库处理管线

## When to load

- 需要将课程/学习资料（音频、视频、PDF）自动转化为 Obsidian 知识库笔记时
- 需要配置 Obsidian 插件（QuickAdd、cmdr、obsidian-git、spaced-repetition 等）时
- 需要增强 Obsidian UI（CSS、动画、主题）时
- 处理 Windows 环境下 Obsidian 的路径/BOM 问题时

## Core workflow patterns

### 1. Pipeline stages

```
1. 素材识别    → 素材类型清单
2. 转写/OCR   → 音频 whisper → txt, 视频 ffmpeg+whisper → txt, PDF pytesseract → json
3. 核验       → 文档页码/ASR 时间戳/源图片作为一手证据；多源内容逐事实对比
4. 总结       → 逐节课结构化总结，保留 source_file、页码/时间戳与处理器
5. 卡片       → 只从已核验内容生成知识卡片 + 复习卡片
6. 入库       → 写入当前项目约定的课程库路径；“全部开始/执行”时自主全量推进，不分步确认
7. 导入报告   → 写入项目约定的执行记录目录，并生成文件级 manifest
8. 完整性校验 → 分开统计源文件覆盖、页数/OCR、ASR 时长、证据图、外链、逐事实验证、人工复核；模板存在不算完成
9. 清理       → 中间文件移入全局归档/质量隔离区，正式课程页通过索引回链；不得删除唯一证据
```

### 2. Chinese OCR & ASR toolchain (2026-07)

**OCR for scanned PDFs — CRITICAL: detect before extract:**

ALWAYS test first page with `fitz.get_text()` before deciding extraction method:
```python
doc = fitz.open(pdf)
test = doc[1].get_text()  # page 1 (skip cover)
if len(test) < 100:
    # SCANNED PDF — MUST use OCR, fitz will not find text
    # DO NOT report as "watermark" — the user can SEE the content
    use_easyocr(pdf)
else:
    use_fitz(pdf)  # text PDF
```

| Tool | Accuracy policy | Notes |
|---|---|---|
| **EasyOCR** | 必须用本库人工样本实测 | Windows CPU 主链；用 `fitz.get_pixmap()`，无需 Poppler |
| PaddleOCR | 不写固定结论 | 可作为备选；是否可用以当前环境实测为准 |
| Tesseract | 必须实测 | 中文质量常低，只作备用 |

不要只测一页后把整份 PDF 固定为“文字版/扫描版”。正确方法是**逐页检测**：文字层足够则原生提取，文字层不足则对该页 OCR。封面也不得无证据跳过。

```python
for page_no, page in enumerate(doc, 1):
    text = page.get_text().strip()
    if len(text) < 80:
        text = easyocr_page(page)
        method = "easyocr"
    else:
        method = "pymupdf"
    write_page_with_provenance(page_no, method, text)
```

**ASR for video/audio:**

- FunASR SenseVoice 可作中文主链，faster-whisper 可作备用，但**不得写固定 CER/准确率**。
- 必须处理完整时长或明确记录已处理时段；“每门前三个文件/每个前 90–120 秒”只能称抽样。
- 长音视频按固定时长分段，产物保留源文件、段起止时间和处理器；文件级 manifest 支持断点续跑。

**Watermark handling — conservative only:**

- 先识别水印的精确文本或版面区域；不得使用 `.*` 把水印后的整行/整页正文删除。
- 显示标题可清理分发前缀，真实源路径保存在 manifest/provenance；如需隐藏，使用“分发标识已隐藏”，不要破坏可恢复性。
- 清理前保存原文到全局质量隔离区，清理后抽样对照源页。

**Content formatting rules:**

1. 去除明确的模型控制标记，但保留真实正文和时间戳。
2. 按源材料的章节、讲次、页码和语义边界重组，不按固定字符数机械切段。
3. 只加粗经术语提取或人工确认的概念；禁止用任意 `[\u4e00-\u9fff]{2,4}` 正则批量加粗。
4. 原始 OCR/ASR 长文放全局归档，正式课程目录保留结构化总结和索引。
5. 主页只做导航；重构前主页先逐门归档，确保可逆。

**Content-matched screenshots (not random keyframes):**
1. Extract key terms from **summaries** (not metadata/titles)
2. Filter stopwords: 可以,需要,一个,什么,进行,使用...
3. Search terms in PDF → screenshot matching page
4. Search terms in ASR timestamps → ffmpeg extract frame at that timestamp
5. Embed in course page under `## 内容证据截图` with source citation

**Multi-source cross-comparison (PDF + ASR):**

文件数量和词频重叠率只能用于筛选候选，不能直接得出“重复”或“互补”。正确步骤：

1. 为每个源文件保留 `source_file`、页码/时间戳和提取器。
2. 按章节/事实单元对齐 PDF、OCR、ASR，而不是只比 top-N 词频。
3. 分别记录：共同结论、矛盾点、仅文档出现、仅音视频出现、无法确认。
4. 每个“互补”结论必须列出双方的具体章节和证据位置。
5. 低重叠只表示“需要检查”，不能自动标注互补。
6. 写入验证页时区分自动候选、已核验结论和待人工复核。

**DOC format limitation:**
Old Chinese .doc (OLE) not readable by antiword/pandoc. LibreOffice headless needed but MSI install problematic on Windows. Known limitation.

### 3. Content filtering rules

未来课程处理时，自动过滤以下非核心内容（不写入正式笔记）：

| 过滤类型 | 示例 | 处理 |
|:---|:---|---:|
| 学员个人分享 | 姓名 + 具体学习经历 | 不写入，报告记录"有学员分享" |
| 获奖名单/作品 | Q&A 大赛获奖者 | 不写入 |
| 运营信息 | "扫码加小助手微信" | 不写入 |
| 打卡抽奖 | "打卡赢奖品" | 不写入 |
| 保留内容 | 老师主线讲解 + 方法 + 术语 + 操作流程 | 完整保留 |

**写报告：** 过滤了什么 + 为什么过滤，写入导入报告。

### 4. Obsidian plugin fixes

常见的插件故障及修复：

| 插件 | 故障 | 修复 |
|:---|:---|:---|
| cmdr | `leftRibbon.forEach is not a function` | `data.json` 中 `leftRibbon` 是 dict 而非 array → 改为 `[]` |
| spaced-repetition | `this.list.splice is not a function` | `data.json` 缺少 `questionPostponementList: []` |
| omnisearch | `Cannot read properties of undefined` | 清空 `.obsidian/plugins/omnisearch/cache/` |
| tasks-plugin | `Unexpected failure to create list item` | 无害 warn（非任务行如 dataview/标题也会报） |
| BOM 问题 | Obsidian 报 "failed to read JSON" | 杀 YunDetectService 进程或重启 |

### 5. QuickAdd template registration

QuickAdd 模板注册在 `.obsidian/plugins/quickadd/data.json`。choices 数组结构：

```json
{
  "choices": [
    {
      "id": "uuid",
      "name": "📚 课程总览",
      "type": "Template",
      "command": false,
      "templatePath": "90_模板/课程处理/课程总览模板.md",
      "folder": "02_课程库"
    }
  ],
  "templateFolderPath": "90_模板"
}
```

注册新模板时，必须同步更新 QuickAdd `data.json`。

### 6. Windows-specific notes

| 问题 | 处理 |
|:---|:---|
| 写入 E 盘 | Python 可以直接写，Node.js REPL 报 EPERM |
| PowerShell 5.1 | 不支持 `&&`（用 `;` 或 `if`），不支持 `utf8BOM`（用 `-Encoding UTF8`） |
| MSYS 路径含中文冒号 | Python 原生 Windows 路径优于 MSYS 路径 |
| Git LFS | 大文件（mp3/mp4/pdf）按 `.gitignore` 排除，不进 Git |
| obsidian-git | 配置 30min 自动 commit，不推远程 |

## Obsidian Compatibility Audit (Adapter vs Full Compatibility)

当用户询问“现在是否全面兼容 Obsidian”或要求验收 Obsidian 集成时，不得把存在 importer/projection 文件、fixture/schema 或单元测试写成全面兼容。先建立分维度矩阵，并逐项追踪真实入口、实现、测试和 E2E 证据：

| 维度 | 必查证据 | 只能如何表述 |
|---|---|---|
| Markdown 文件 | `.md` 读取、编码、目录递归、真实回读 | 支持哪些 Markdown 文件流 |
| YAML/frontmatter | 完整 YAML parser、数组/嵌套/日期/插件字段 fixture | 基础解析或完整兼容 |
| Wikilink/引用 | `[[link]]`、alias、heading/block ref、embed、rename/delete 规则 | 部分链接解析或完整语义 |
| 资源 | 图片/PDF/音视频、附件相对路径、哈希和移动 | 文本导入或含资源闭环 |
| Obsidian 专属格式 | Canvas、Excalidraw、Bases、properties | 已支持、只保留原文、或未支持 |
| 插件语义 | Dataview、Tasks、Templater、QuickAdd、Meta Bind 等 | 不要把插件名称吸收写成运行时兼容 |
| 写入/投影 | dry-run 默认、approved root、原子写入、冲突与回滚 | 受治理投影，不等于双向同步 |
| 同步 | 文件监听、增量、rename/delete、冲突、幂等和恢复 | 手动 import/export 或实时双向同步 |
| 真实验收 | 隔离 fixture、真实 Vault（须用户明确授权）、前后端/文件回读 | 代码存在、fixture 通过或真实 E2E，分别标注 |

先读 API 路由和 public entrypoint，再读 importer/projection 的完整调用路径，最后查专门测试与 CI。若只有 `shared/obsidian_importer.py`、projection renderer、schema fixture 或未勾选 checklist，应归类为 **partial adapter**，不能归类为 full compatibility。明确检查是否只支持 `.md`、是否使用简化 frontmatter parser、是否跳过 `.obsidian`/模板/报告目录、是否默认 dry-run、是否要求显式 `vault_root`。

安全边界：不默认访问用户个人 Vault，不扫描或修改外部 Obsidian 项目；只有用户在当前请求中给出精确路径和操作授权时，才对真实 Vault 做隔离、只读优先的验收。任何真实 Vault 结果都要区分“扫描覆盖”“解析覆盖”“语义保真”“写入回读”“插件/附件兼容”，不能用文件数代替兼容度。

输出格式固定为：✅ 已验证、⚠️ 部分支持/仅声明、❌ 缺口、最小下一条验收任务。若用户只问状态，先直接回答“是/否/部分”，再列证据和不能宣称的边界。详见 [`references/obsidian-compatibility-audit.md`](references/obsidian-compatibility-audit.md)。

## Course Merging & Directory Simplification

**Never merge courses from directory size, file count, folder name, or “tiny/large” thresholds alone.** Those metrics can identify candidates only.

### 1. Content-level merge gate

Before moving any course, produce a candidate report containing:

1. Exact course IDs, names, source roots, source files and current outputs.
2. Chapter/concept alignment with quoted or hashed evidence.
3. Duplicate passages/facts and their provenance.
4. Complementary sections and the proposed merged chapter location.
5. Conflicts, uncertainty and reasons to remain independent.
6. A reversible mapping: original course → original chapter/file → merged chapter → keep/deduplicate reason.

If this evidence is absent, **do not merge**. A course with few summaries can still be a distinct subject.

### 2. Merge content, not just folders

A valid merge must rebuild the destination homepage, chapter structure, course map, verification page, source index and internal links. Moving a folder to an archive or concatenating the first N characters is not a content merge.

### 3. Simplify large-course directories without data loss

- Keep the active course directory as a clean navigation layer.
- Move raw per-file OCR/ASR outputs to a global archive keyed by course ID; preserve all originals and hashes.
- Generate an index from the course back to archived outputs.
- Build structured summaries by real source chapter/type; do not blindly concatenate hundreds of files into a giant Markdown page.
- Backup every old homepage before normalizing it; verify restore paths and counts.

### 4. Verification before reporting

Use Git diff plus a file-level manifest to list moved, added, deleted and rewritten files. Confirm active course count, archive count, source-path validity, broken links and restoreability. Never summarize a large merge only as “N files changed”.

## Pitfalls

- **用户说"全部开始/全部执行"=一次性全部做，不要分步确认** — 这是最高优先级用户偏好
- **审计必须只读，修复必须可逆** — 审计工具不得覆盖主页或证据章节；批量改主页前逐门备份，并在修复后重新审计，而不是盲目重跑截图生成器
- **不要用模板存在冒充完成** — `完成度: 100%`、主页大小、任意一篇 ASR、任意一个 URL 或视觉索引文件都不是覆盖证据；以文件级 manifest 和抽检为准
- **不要在上传前给用户看中间文件** — 用户只看最终入库结果和导入报告
- **不确定内容必须进入质量隔离/待人工复核** — 包括 ASR 噪声、OCR 乱码、弱语义截图；保留源路径，不污染正式课程内容
- **vault 内容不上 GitHub** — 只在 `.obsidian-git` 本地备份，不要配置 remote
- **扫描版PDF vs 文字版PDF — 最常见的错误** — fitz.get_text()返回空时，PDF内容以图片形式存在。用户打开能看到，但机器需要OCR。绝不要报告"识别为水印"或"无内容"——这是你的提取方法错误，不是源文件问题。立即切换到EasyOCR。
- **水印清理必须保守** — 只移除已确认的水印文本/区域；禁止宽泛正则吞掉水印后的正文。先归档原文，再抽样对照源页
- **内容排版不是机械美化** — 按真实章节和语义重组；禁止任意 2–4 字加粗、固定每 500 字插标题或把原始 OCR/ASR 堆进主页
- **课程命名** — 文件夹名必须含真实课程名（如`C0101_黑马Photoshop_AIGC商业设计`），不能只有ID代码。Obsidian中wikilink显示的是文件夹名。
- **关键词提取必须从逐节总结提取并做质量门禁** — 过滤“其他/素材/资料/课程”等通用词；弱匹配进入质量隔离，不能当内容证据
- **入库后检查完整性** — URL 存在只代表有参考链接；逐事实验证必须绑定具体结论、URL、访问日期和源页/时间戳
- **断链审计禁止路径链接的全局 stem 兜底** — 含 `/` 的目标必须按绝对/相对精确路径解析；只有不含 `/` 的简单 wikilink 才允许按 stem 模糊解析，否则会把真实断链误报为 0
- **审计快照必须稳定** — 同步、OCR/ASR 或其他写入仍在修改 vault 时，停止并发写入并重跑基线；不得混用修复前后的统计
- **准确率与外部验证必须可复现** — 无人工 truth/prediction 对时状态为 `unverified`；静态权威 URL 注册表只能叫推荐来源，不能叫完成验证
- **准确率 ≠ 只讲 CER/WER（本用户铁律，2026-08）** — 当用户问"怎么保证准确率"时，不要只答 OCR/ASR 的 CER/WER（那只是识别转译层）。对**公开内容（书、通用资料）**，准确率保证机制是**全网交叉对比**：用公开权威来源（Wikipedia REST API、官方文档、百科、教材、图书馆/学术数据库）核验内容里的可查证事实。这条对所有格式（PDF/图片/音频/视频/Office）适用，识别转译之后都要做。识别转译置信度**永不**当作内容事实准确性。
- **两层验证模型（缺一不可，不混用）** — ①识别转译层：高精度模型（OCR/ASR/多格式提取）+ CER/WER 金标准对；②内容事实层：全网交叉对比（全格式通用，核心）。交叉对比只核验可查证事实（年份/人名/概念/数字/理论归属），不核验口语/转译噪声/私密记录；书为近似表述时记录"书 vs 权威精确值"差异（如"20世纪20年代"→"1929年"）不直接改正文；与权威源冲突→记录差异不自动覆盖；存疑进人工复核队列。权威来源层级+书籍场景速查见 `obsidian-web-crosscheck` 技能的 `references/authoritative-source-hierarchy.md`。
- **识别转译管线设计：分叉+门控+解耦（2026-08 评审）** — 用户提出"外置识别→模型辅助→模型识别→全网验证"线性瀑布；评审建议改为分叉+门控+解耦避免每份文件逐级爬：文字型（markitdown/trafilatura）、扫描型（OCR，置信度不够才上 LLM）、音视频（ASR，CER 不够才上 LLM）按格式分叉；识别层与全网验证层解耦；不可查证内容跳过验证标"无法全网验证"；人工复核兜底。评审提示词与管线全景清单存于项目 `.hermes/task-runtime/`（`pipeline-review-prompt.md`、`project-pipelines-inventory.md`）。
- **CHANGE_PROPOSAL 登记后才执行（本用户/项目铁律，2026-08）** — 增强任务包（如 AXW-MFX-WXV-v1）在所有者批准前**不具执行权威**，只允许：登记为 append-only 记录、审计、估算、任务拆分。批准前绝不修改仓库能力/远端/用户数据/发布物。收到任务包先做 MFX-000 式登记（绑定当日 main SHA、存档 SHA、owner 状态 PENDING），再向所有者呈现批准项清单，批准后才执行。
- **PDF.js 静态前端集成（无 npm 的 Python wheel 前端，2026-08）** — 纯静态 JS 前端（无 import/require、无 npm 构建，经 `pyproject.toml [tool.setuptools.package-data]` 打包）集成 PDF.js：① 下载 pdf.min.js + pdf.worker.min.js 到 `app/workspace/ui/assets/`，**末尾必须补 LF 换行**否则 `check_repository_conventions.py` 报 `missing-final-newline`；② package-data 需加 `ui/assets/licenses/*.txt` 并把 LICENSE 存进 `licenses/` 子目录（Apache-2.0 需审计进 THIRD_PARTY_NOTICES）；③ assets 路由 `Literal[...]` 白名单要加新文件名（否则运行时 422/404）；④ **workerSrc 必须惰性配置**（放 loadPdf 闭包内、定义时仅赋值），不要在 index.html 用内联 `<script>` 配 workerSrc——内联配置会让页面加载时 PDF.js 初始化 worker，污染 browser-smoke 的 console_errors 断言（`assert not console_errors` 失败）；⑤ 若既有测试断言 package-data 精确字符串（`test_workspace_runtime_assets_are_packaged`），改 package-data 必须同步更新该断言。验证：node --check 查 JS 语法、TestClient 查资产 200、真实浏览器导航查 `pdfjsLib.version`。
- **Honest-capability guard：禁止 metadata-only 冒充内容成功（MFX-010，2026-08）** — 多格式转换引擎链里，元数据适配器（Pillow 尺寸/EXIF、FFprobe 容器信息）**绝不能作为内容转换成功**。常见根因：引擎链把 metadata adapter 排在真实引擎前，且 `convert_file` 的"第一个 `success=True` 即返回"逻辑让图片/媒体从元数据假成功，阻断了实际 OCR/ASR。修复三件套：① 内容后置条件——只有 `success and content.strip()` 非空才算成功，空/占位结果 fail-closed 报错（`reason = result.error or "returned empty content"`）；② 引擎链用真实内容引擎（image→tesseract+pytesseract，检测不到则返回明确的 unavailable 错误，不 success）打头，把 metadata adapter 移出内容成功路径；③ 修正模块 docstring——如实写"无 Tesseract 则 OCR 不可用/媒体仅 metadata 无 ASR"，绝不写"支持 OCR"却只跑元数据。回归测试：无 OCR 引擎时图片必须 fail-closed、引擎链首个引擎非 metadata、空内容不算成功。\n- **Legacy 启发式隔离：启发式分数永不升级 verified 状态（MFX-012，2026-08）** — 域名/关键词可信度启发式（如 `score_credibility`：可信域名后缀、"peer-reviewed"字样、DOI 形状子串加分）**只作内部排序提示**，绝不写入 EvidenceBundle/CrossValidation/verified/web-verified/evidence 状态。做法：① 返回结构加 `classification="legacy_heuristic"` 字段 + docstring 显著警告；② 消费端（如 pipeline 的 crossref stage）强制 `classification="legacy_heuristic"` + `verified=False`，使旧分数永远读不出"已全网验证"；③ 回归测试断言可信域+"peer-reviewed"+DOI 仍返回 `legacy_heuristic` 且非 verified。真正的事实验证走 EvidenceConnector/obsidian-web-crosscheck，不依赖此启发式。\n- **供应链台账：结构化 gate + 代码/模型许可分离（MFX-001，2026-08）** — 为依赖/组件建机器可读台账（如 `docs/truth/SUPPLY_CHAIN_LEDGER.json`），每组件记录 `code_license` 与 `model_license`（**分开**，不合并）和 `gate: approved|review_required|blocked`。approved=已审默认可用；review_required=能力探针不得默认启用（docling/paddleocr/faster-whisper/ffmpeg 需 build-audit 等）；blocked=许可禁止默认（MinerU/PyMuPDF/Marker/FunASR/SearXNG/Zotero）。回归测试：台账是合法 JSON、gate 全在闭集、已知 blocked 组件必须 present 且 blocked、blocked 组件不得出现在默认引擎链、默认引擎链组件 gate≠blocked。能力声明由安装证据/探针决定，台账 gate 不授权分发。\n- **DOC老格式** — 为每个文件记录当前处理器结果和失败原因；不要把某次环境失败固化成永久能力结论
- **多格式引擎链真实素材测试（2026-08-13 实测修复集）** — 用真实资料库（用户课程库 + 网上样本）按格式矩阵逐类打 `/convert/file` 后发现的五个修复点：① **markitdown extras 不覆盖全部引擎链**——pyproject 只声明 `markitdown[pdf]` 时 docx/pptx/xlsx 全部报 `MissingDependencyException`（`No engine could convert ...`）；引擎链 `_ENGINES` 声明了哪些格式，pyproject 就必须声明对应 extras（`markitdown[pdf,docx,pptx,xlsx]`，extra 名在 PyPI requires_dist 里查）；② **扫描版 PDF 必须有 OCR 兜底引擎**——markitdown 对无文字层 PDF 返回空、docling 未装即失败；加 `_via_pdf_ocr`（pymupdf/fitz 逐页 `get_pixmap(dpi=200)` 渲染 → pytesseract `lang="chi_sim+eng"`，每页输出 `<!-- page N -->` 锚点，全空则 fail-closed）；③ **GBK/GB2312 中文 txt 按 UTF-8 读必乱码**——`_decode_text_bytes` 编码级联（utf-8 严格 → gb18030 → utf-16 → latin-1 兜底），禁止 `errors="ignore"/"replace"` 直接读；④ **Magika 会把 GBK 文本误判为 csv/html**（置信度 0.7+ 照样错）——文本格式（txt/md/csv/tsv）必须**扩展名优先**，内容检测只用于无扩展名/二进制格式；⑤ **ingest_file 必须接入引擎链**——只读 md/txt 的 ingest 遇到 pdf 报 `unsupported file extension`，把 `DEFAULT_EXTENSIONS` 对齐 `_ENGINES` 全集，`_read_text` 对富格式走 `convert_file`（转换失败转 `IngestionError`，空内容也 fail-closed）。测试矩阵本身：每个格式记录 `engine` + `char_count`，扫描版/文字版 PDF 分开算，全绿后跑全量 pytest（改 pyproject 后 requirements.txt 声明式同步 + release-manifest digest 重算 + a0-gates 断言锁步更新）。
- **多源课程必须逐内容对比** — 词频重叠只用于候选筛选；“互补”必须有双方章节/事实证据
- **旧媒体/TS逐文件诊断** — 用 ffprobe/ffmpeg 记录容器、可解码性和错误；只有实际证据支持时才能标注加密、损坏或不可解码

## References

- `references/cross-comparison.md` — 多源交叉对比脚本和逻辑
- `references/pipeline-reference.md` — 管道各阶段详解
- `references/toolchain-2026-07.md` — 完整工具链参考
- `references/public-content-web-crosscheck.md` — 公开书籍/通用资料的批量全网交叉对比配方（Wikipedia REST API + 权威层级 + 可信度等级 + 已验证案例）
- `references/mfx-multiformat-pipeline-architecture.md` — AXW-MFX-WXV-v1 方案 C 持久化设计：RawAsset-first + 页/区段路由 + 校准门控 + 选择性引擎/LLM 升级 + Claim 级异步验证 + 人工授权；对象复用矩阵、默认引擎、批次依赖、停止条件（所有者 2026-08 批准）
- `references/mfx-batch0-stop-loss-patterns.md` — MFX-010/012/001 止损实现配方：honest-capability guard（metadata-only 不冒充内容成功）、legacy 启发式隔离、结构化供应链台账 gate；含代码片段与回归测试写法
- `references/evidence-driven-audit-and-repair.md` — 文件级真实审计、内容级合并门禁、可逆修复和证据图质量门禁
- `references/evidence-integrity-audit.md` — 稳定快照、精确断链解析、YAML/Dataview 门禁、golden-set 准确率和最终验收清单
